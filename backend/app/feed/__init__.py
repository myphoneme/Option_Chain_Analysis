from typing import Optional

from app.config import settings
from .base import FeedAdapter, Instrument, NormQuote  # noqa: F401
from .token_provider import InternalTokenProvider, TokenError  # noqa: F401
from .xts import XTSAdapter, XTSError  # noqa: F401
from .xts_direct import XTSDirectAdapter  # noqa: F401


_direct_singleton: Optional[XTSDirectAdapter] = None


def build_adapter(access_token: Optional[str] = None) -> FeedAdapter:
    """Return the configured feed adapter.

    - direct mode (default): server-to-server XTS via the internal token
      (rich data incl. OI). No per-user token needed. Returned as a process
      singleton so the token and the (daily) instrument master stay cached.
    - proxy mode: legacy per-user gateway proxy (needs access_token cookie).
    """
    global _direct_singleton
    if settings.XTS_MODE == "direct" and settings.has_app_credentials():
        if _direct_singleton is None:
            _direct_singleton = XTSDirectAdapter()
        return _direct_singleton
    return XTSAdapter(base_url=settings.GATEWAY_BASE, access_token=access_token)
