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
