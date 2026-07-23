"""Configuration + minimal .env loader (no external dependency).

Secrets (XTS app key/password) come from environment variables, sourced from a
gitignored `.env` file. Never hardcode credentials in tracked source.
"""
from __future__ import annotations

import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from backend/.env into os.environ (no overwrite)."""
    env_path = _BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv()


class Settings:
    # QuantTrade gateway
    GATEWAY_BASE = os.getenv("QT_GATEWAY_BASE", "https://quantapi.phoneme.in")
    # Internal app credentials (Basic Auth) for the XTS token endpoint
    XTS_APP_KEY = os.getenv("XTS_APP_KEY", "")
    XTS_APP_PASSWORD = os.getenv("XTS_APP_PASSWORD", "")
    XTS_TOKEN_PATH = os.getenv("XTS_TOKEN_PATH", "/api/internal/xts/marketdata/token")
    # Direct XTS MarketData base (IIFL)
    XTS_MD_BASE = os.getenv("XTS_MD_BASE", "https://ttblaze.iifl.com/apimarketdata")
    # "direct" = call XTS at ttblaze with an internal token (rich data incl. OI).
    # "proxy"  = legacy per-user cookie proxy on the gateway (no OI).
    XTS_MODE = os.getenv("XTS_MODE", "direct")

    @classmethod
    def has_app_credentials(cls) -> bool:
        return bool(cls.XTS_APP_KEY and cls.XTS_APP_PASSWORD)


settings = Settings()
