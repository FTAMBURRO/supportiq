"""Flask CLI commands (``flask seed``)."""

import click
from flask import current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Category, User
from app.repositories.category_repository import CategoryRepository
from app.repositories.user_repository import UserRepository

# Development reference data only: no secrets, just readable entities.
_CATEGORIES = [
    ("Access", "access", "Accounts, logins and permissions"),
    ("Hardware", "hardware", "Laptops, monitors and peripherals"),
    ("Software", "software", "Applications and installations"),
    ("Network", "network", "Connectivity, VPN and Wi-Fi"),
    ("Billing", "billing", "Invoices and payments"),
    ("Other", "other", "Anything that does not fit above"),
]

_USERS = [
    ("ana.dev@supportiq.local", "Ana Dev"),
    ("bruno.dev@supportiq.local", "Bruno Dev"),
    ("carla.dev@supportiq.local", "Carla Dev"),
]


@click.command("seed")
@with_appcontext
def seed():
    """Insert development categories and users. Idempotent: running it
    twice leaves the same rows, it never duplicates them."""
    category_repo = CategoryRepository()
    user_repo = UserRepository()

    created_categories = 0
    for name, slug, description in _CATEGORIES:
        if category_repo.get_by_slug(slug) is None:
            db.session.add(
                Category(name=name, slug=slug, description=description)
            )
            created_categories += 1

    created_users = 0
    for email, full_name in _USERS:
        if user_repo.get_by_email(email) is None:
            db.session.add(User(email=email, full_name=full_name))
            created_users += 1

    db.session.commit()
    current_app.logger.info(
        "seed: %s categories and %s users created",
        created_categories,
        created_users,
    )
    click.echo(
        f"Seed complete: {created_categories} categories, "
        f"{created_users} users created."
    )
