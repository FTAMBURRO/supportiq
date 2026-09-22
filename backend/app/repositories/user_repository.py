"""Persistence for users."""

import uuid

from app.extensions import db
from app.models import User


class UserRepository:
    """SQL queries for users. Stateless: uses the app-scoped session."""

    def get(self, user_id: uuid.UUID) -> User | None:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        query = db.select(User).where(User.email == email)
        return db.session.execute(query).scalars().first()
