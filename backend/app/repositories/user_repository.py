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

    def list_active(self) -> list[User]:
        """Active users ordered by display name.

        Reference data for the UI (requester/assignee selects and
        id-to-name resolution). Inactive users are excluded: they can
        no longer be chosen for anything.
        """
        query = (
            db.select(User)
            .where(User.is_active.is_(True))
            .order_by(User.full_name.asc(), User.email.asc())
        )
        return list(db.session.execute(query).scalars().all())
