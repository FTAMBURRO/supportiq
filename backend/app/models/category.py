"""Category model."""

import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class Category(TimestampMixin, db.Model):
    """A functional support category (e.g. Access, Hardware, Billing).

    Stored as data rather than an enum so categories can later be
    administered, used by the AI classifier, and varied per
    organization. Categories are deactivated with ``is_active`` rather
    than deleted.
    """

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="category"
    )

    @validates("slug")
    def _normalize_slug(self, _key: str, value: str) -> str:
        """Trim, lowercase and verify the slug is url-friendly."""
        slug = value.strip().lower()
        if not _SLUG_RE.fullmatch(slug):
            raise ValueError(f"invalid slug: {value!r}")
        return slug
