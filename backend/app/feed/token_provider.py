"""Internal XTS MarketData token provider.

Implements the SOP in `internal_xts_token_sop.md`: authenticate to the gateway
with HTTP Basic Auth (app key/password) and receive a short-lived XTS MarketData
token, which is then used against XTS directly.

Token handling rules (from the SOP):
- cache the token; do not request one before every call;
- refresh only when expiry is near (< REFRESH_MARGIN s left);
- on an unauthorized XTS call, force one refresh and retry.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

import requests

from app.config import settings

_TOKEN_CACHE = Path(__file__).resolve().parent.parent.parent / "data" / "xts_token.json"


class TokenError(RuntimeError):
    """Raised when a token cannot be obtained; message is user-actionable."""


class InternalTokenProvider:
    REFRESH_MARGIN = 120      # seconds before expiry to proactively refresh
    MIN_MINT_INTERVAL = 30    # never mint twice within this window (gateway 429s)

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_password: Optional[str] = None,
        gateway_base: Optional[str] = None,
        token_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = 20.0,
        cache_path: Optional[Path] = _TOKEN_CACHE,
    ):
        self.app_key = app_key or settings.XTS_APP_KEY
        self.app_password = app_password or settings.XTS_APP_PASSWORD
        self.gateway_base = (gateway_base or settings.GATEWAY_BASE).rstrip("/")
        self.token_path = token_path or settings.XTS_TOKEN_PATH
        self._session = session or requests.Session()
        self.timeout = timeout
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._issued_at: float = 0.0
        self._lock = threading.Lock()
        self._cache_path = cache_path   # None disables the on-disk cache (tests)
        self._load_cache()

    def _load_cache(self) -> None:
        """Reuse a still-valid token across process restarts (saves mint quota)."""
        if self._cache_path is None:
            return
        try:
            obj = json.loads(self._cache_path.read_text())
        except (OSError, ValueError):
            return
        if obj.get("key") == self.app_key and obj.get("expires_at", 0) - time.time() > self.REFRESH_MARGIN:
            self._token = obj.get("token")
            self._expires_at = float(obj["expires_at"])
            self._issued_at = float(obj.get("issued_at", 0))

    def _save_cache(self) -> None:
        if self._cache_path is None:
            return
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps({
                "key": self.app_key, "token": self._token,
                "expires_at": self._expires_at, "issued_at": self._issued_at,
            }))
        except OSError:
            pass

    def _seconds_left(self) -> float:
        return self._expires_at - time.time()

    def _fresh(self) -> bool:
        return bool(self._token) and self._seconds_left() > self.REFRESH_MARGIN

    def get_token(self, force: bool = False, stale_token: Optional[str] = None) -> str:
        # Fast path: valid cached token, no lock needed.
        if not force and self._fresh():
            return self._token
        with self._lock:
            # Re-check inside the lock — another thread may have just refreshed.
            if not force and self._fresh():
                return self._token
            # Forced refresh after an 'Invalid Token': if another thread already
            # replaced the failed token, reuse theirs instead of minting again
            # (XTS is single-session — concurrent mints invalidate each other).
            if force and stale_token is not None and self._token not in (None, stale_token):
                return self._token
            # Throttle only PROACTIVE refreshes — the gateway 429s if we mint too
            # often. A forced refresh follows an explicit "Invalid Token" from XTS,
            # where minting again is exactly the right recovery, so it is exempt
            # (the stale_token guard above already stops duplicate concurrent mints).
            if (not force and self._token
                    and (time.time() - self._issued_at) < self.MIN_MINT_INTERVAL):
                return self._token
            try:
                return self._request_token()
            except TokenError:
                # Rate-limited or transient: a token that has not actually
                # expired is still usable — prefer it over failing the request.
                if self._token and self._seconds_left() > 0:
                    return self._token
                raise

    def _request_token(self) -> str:
        if not self.app_key or not self.app_password:
            raise TokenError(
                "XTS app credentials are not configured. Set XTS_APP_KEY and "
                "XTS_APP_PASSWORD (backend/.env)."
            )
        url = f"{self.gateway_base}{self.token_path}"
        try:
            r = self._session.post(
                url, auth=(self.app_key, self.app_password), timeout=self.timeout
            )
        except requests.RequestException as e:
            raise TokenError(f"Could not reach the token endpoint: {e}") from e

        if r.status_code == 404:
            raise TokenError(
                "Token endpoint returned 404. The gateway has not enabled "
                "ENABLE_INTERNAL_XTS_TOKEN_API=true. Ask the QuantTrade admin to "
                "enable the internal XTS token API for this app."
            )
        if r.status_code == 401:
            raise TokenError(
                "401 Invalid internal app credentials — APP_KEY/APP_PASSWORD is "
                "wrong or the app is disabled (Admin Apps)."
            )
        if r.status_code == 403:
            raise TokenError(
                "403 Internal app scope not allowed — the app credential lacks the "
                "'xts:marketdata:token' scope."
            )
        if r.status_code == 429:
            raise TokenError("429 XTS token rate limit exceeded — cache and retry later.")
        if r.status_code in (502, 503, 504):
            # Distinguish "gateway app is down" (nginx serves an HTML error page)
            # from "gateway is up but XTS upstream failed" (JSON error body).
            body = (r.text or "")[:300].lower()
            if "<html" in body or "nginx" in body or "bad gateway" in body:
                raise TokenError(
                    f"The QuantTrade gateway is DOWN (nginx {r.status_code}, no app response "
                    f"at {self.gateway_base}). This is not a credentials problem — the API "
                    "server behind nginx needs to be restarted by the gateway team. "
                    "Case-study scripts still work offline."
                )
            raise TokenError(
                f"{r.status_code} — the gateway is up but could not obtain an XTS "
                "MarketData token (XTS service/credentials issue upstream)."
            )
        if r.status_code >= 400:
            raise TokenError(f"Token endpoint HTTP {r.status_code}: {r.text[:200]}")

        try:
            data = r.json()
        except ValueError as e:
            raise TokenError(f"Token endpoint returned non-JSON: {r.text[:200]}") from e

        token = data.get("token")
        if not token:
            raise TokenError(f"Token endpoint response had no token: {data}")
        expires_in = float(data.get("expiresInSeconds", 1200))
        now = time.time()
        self._token = token
        self._expires_at = now + expires_in
        self._issued_at = now
        self._save_cache()
        return token

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0
