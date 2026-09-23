"""Gunicorn configuration for production runs (Fase 6).

Gunicorn itself is POSIX-only: this config is exercised on the Linux
deploy target (Render) and inside the Linux container used for the
local production smoke test — not on the Windows dev machine, where
the Flask development server still applies.

PORT is injected by the platform (Render exports ``$PORT``); local
smoke tests export it too. The production port is never hardcoded.
"""

import os

# 0.0.0.0 so the platform router can reach the app; PORT comes from
# the environment (default only for local smoke tests).
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# The free tier starts at 512 MB: one sync worker keeps the footprint
# minimal and demo traffic never justifies more. USD 0.
workers = 1
