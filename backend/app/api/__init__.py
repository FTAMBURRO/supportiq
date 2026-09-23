"""HTTP routes (API layer).

Routes stay thin: they parse input, call a service and serialize the
response. Business logic lives in ``services`` and SQL lives in
``repositories``.
"""

from flask import Blueprint, jsonify

from app.errors import ApiError

api = Blueprint("api", __name__, url_prefix="/api")


@api.errorhandler(ApiError)
def handle_api_error(error: ApiError):
    """Render every ApiError with the approved JSON envelope."""
    return jsonify(error={"code": error.code, "message": error.message}), (
        error.status_code
    )


from app.api import health  # noqa: E402, F401  (registers /api/health)
from app.api import tickets  # noqa: E402, F401  (registers /api/tickets)
from app.api import dashboard  # noqa: E402, F401  (registers /api/dashboard)
from app.api import users  # noqa: E402, F401  (registers /api/users)
from app.api import categories  # noqa: E402, F401  (registers /api/categories)
