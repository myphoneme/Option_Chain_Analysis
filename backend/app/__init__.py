"""Option Chain Analysis backend.

Implements the Professional Scanning Sequence (SOP) from Module 5, Lesson 1
as an executable decision-support engine.
"""

# Single source of truth for the engine version. Surfaced via /health and /meta
# and rendered by the frontend badge, so the displayed version cannot drift.
__version__ = "1.2.0"
