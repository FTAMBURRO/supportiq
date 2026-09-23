"""Same-origin serving of the built React SPA (Fase 6 · Option B).

One public entry point, one origin — deliberately no CORS and no
separate API base URL (the frontend keeps calling ``fetch('/api/...')``):

    GET /api/*   → the existing JSON API (never shadowed by the SPA)
    GET /*       → real files from ``frontend/dist``, with a generic
                   ``index.html`` fallback so React deep links such as
                   ``/tickets/SUP-000001`` survive a refresh.

The fallback is generic — no hardcoded list of React routes — but it
always respects the ``/api`` prefix: unknown API routes keep answering
with the JSON error envelope, and a missing hashed asset answers 404
instead of HTML that a browser would try to execute as JavaScript/CSS.
"""

from pathlib import Path

from flask import Flask, abort, current_app, send_from_directory
from werkzeug.exceptions import NotFound


def register_spa(app: Flask) -> None:
    """Register the SPA routes. Call once, after the API blueprint."""

    @app.get("/")
    def spa_root():
        dist = _dist_dir()
        if dist is None:
            abort(404)
        return _send_index(dist)

    @app.get("/<path:path>")
    def spa_fallback(path: str):
        # /api/* never falls through to the SPA: unknown API routes
        # keep returning the JSON error envelope, not index.html.
        if path.split("/", 1)[0] == "api":
            abort(404)

        dist = _dist_dir()
        if dist is None:
            abort(404)

        # Real files (Vite assets, favicon, ...) win over the fallback.
        # send_from_directory refuses anything outside ``dist`` and
        # raises NotFound for what is not there.
        try:
            return send_from_directory(dist, path)
        except NotFound:
            pass

        # A missing hashed asset must 404 rather than serve HTML that
        # a browser would then try to execute as JS/CSS.
        if path.startswith("assets/"):
            abort(404)

        # Generic SPA fallback: any other unknown path is a React route.
        return _send_index(dist)


def _dist_dir() -> Path | None:
    """Directory of the built SPA; empty config disables serving.

    ``TestingConfig`` clears it so the suite never depends on whether
    ``frontend/dist`` happens to exist on the machine; SPA tests point
    it at a temporary fixture directory instead.
    """
    raw = current_app.config.get("SPA_DIST_DIR")
    return Path(raw) if raw else None


def _send_index(dist: Path):
    if not (dist / "index.html").is_file():
        # No frontend build on disk: an honest JSON 404, never fake HTML.
        abort(404)
    return send_from_directory(dist, "index.html")
