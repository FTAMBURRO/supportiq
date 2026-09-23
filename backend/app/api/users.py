"""User reference endpoint (read-only).

Exists so the UI can pick a requester/assignee and resolve ids to
names. Pure reference data: no service layer (nothing to validate or
decide — the repository already filters and orders), no mutations.
"""

from flask import jsonify

from app.api import api
from app.api.serializers import serialize_user
from app.repositories.user_repository import UserRepository

_user_repo = UserRepository()


@api.get("/users")
def list_users():
    """Active users ordered by name, as a plain JSON array."""
    users = _user_repo.list_active()
    return jsonify([serialize_user(user) for user in users]), 200
