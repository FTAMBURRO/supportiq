"""HTTP routes (API layer).

Routes stay thin: they parse input, call a service and serialize the
response. Business logic lives in ``services`` and SQL lives in
``repositories``.
"""

from flask import Blueprint

api = Blueprint("api", __name__, url_prefix="/api")

from app.api import health  # noqa: E402, F401  (registers /api/health)
