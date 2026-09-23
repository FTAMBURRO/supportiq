"""Category reference endpoint (read-only).

Exists so the UI can filter tickets by category and let a human set or
correct one (the feedback-loop boundary). Pure reference data: no
service layer (nothing to validate or decide), no mutations.
"""

from flask import jsonify

from app.api import api
from app.api.serializers import serialize_category
from app.repositories.category_repository import CategoryRepository

_category_repo = CategoryRepository()


@api.get("/categories")
def list_categories():
    """Active categories ordered by name, as a plain JSON array."""
    categories = _category_repo.list_active()
    return jsonify([serialize_category(c) for c in categories]), 200
