"""Persistence for categories."""

import uuid

from app.extensions import db
from app.models import Category


class CategoryRepository:
    """SQL queries for categories. Stateless: uses the app-scoped session."""

    def get(self, category_id: uuid.UUID) -> Category | None:
        return db.session.get(Category, category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        query = db.select(Category).where(Category.slug == slug)
        return db.session.execute(query).scalars().first()

    def list_active(self) -> list[Category]:
        """Active categories ordered by display name.

        Reference data for the UI (category filter and the human
        correction select). Inactive categories are excluded: they can
        no longer be assigned.
        """
        query = (
            db.select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.name.asc(), Category.slug.asc())
        )
        return list(db.session.execute(query).scalars().all())
