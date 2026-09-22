"""Health check endpoint."""

from flask import jsonify

from app.api import api


@api.get("/health")
def health():
    """Return the service liveness status."""
    return jsonify(status="ok"), 200
