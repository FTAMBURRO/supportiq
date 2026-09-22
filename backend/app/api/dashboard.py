"""Dashboard summary endpoint."""

from flask import jsonify

from app.api import api
from app.services import dashboard_service


@api.get("/dashboard/summary")
def dashboard_summary():
    """Headline counters for the future dashboard, computed in SQL."""
    return jsonify(dashboard_service.summary()), 200
