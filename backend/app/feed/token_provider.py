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

import time
from typing import Optional

import requests

from app.config import settings


class TokenError(RuntimeError):
    """Raised when a token cannot be obtained; message is user-actionable."""


class InternalTokenProvider:
    REFRESH_MARGIN = 120  # seconds before expiry to proactively refresh

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_password: Optional[str] = None,
        gateway_base: Optional[str] = None,
        token_path: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = 20.0,
    ):
        self.app_key = app_key or settings.XTS_APP_KEY
        self.app_password = app_password or settings.XTS_APP_PASSWORD
        self.gateway_base = (gateway_base or settings.GATEWAY_BASE).rstrip("/")
        self.token_path = token_path or settings.XTS_TOKEN_PATH
        self._session = session or requests.Session()
        self.timeout = timeout
        self._token: Optional[str] = None
        self._expires_at: float = 0.0

    def _seconds_left(self) -> float:
        return self._expires_at - time.time()

    def get_token(self, force: bool = False) -> str:
        if not force and self._token and self._seconds_left() > self.REFRESH_MARGIN:
            return self._token
        return self._request_token()

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
        if r.status_code == 502:
            raise TokenError(
                "502 — the gateway could not obtain an XTS MarketData token "
                "(XTS credentials/service issue upstream)."
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
        self._token = token
        self._expires_at = time.time() + expires_in
        return token

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0
