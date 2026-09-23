"""Flask CLI commands (``flask seed``, ``flask embeddings``)."""

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


# --- embeddings (Fase 3: semantic foundation) -------------------------------


@click.group("embeddings")
def embeddings():
    """Embedding maintenance: backfill and semantic search (CLI only)."""


@embeddings.command("backfill")
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=None,
    help="Embed at most N pending tickets this run (default: all pending).",
)
@with_appcontext
def embeddings_backfill(limit):
    """Embed tickets whose embedding is NULL.

    Idempotent and crash-safe: one ticket at a time, one commit per
    ticket, a single failure never aborts the rest, and re-running only
    picks up whatever is still pending. Small batches only — the Gemini
    free tier is limited and SupportIQ costs USD 0.
    """
    from app.repositories.ticket_repository import TicketRepository
    from app.services import embedding_service

    repo = TicketRepository()
    pending = repo.list_pending_embeddings(limit=limit)

    embedded = 0
    failed = 0
    for ticket in pending:
        if embedding_service.embed_and_persist(ticket):
            embedded += 1
            click.echo(f"  {ticket.ticket_number}: embedded")
        else:
            failed += 1
            click.echo(f"  {ticket.ticket_number}: failed (see log warning)")

    remaining = repo.count_pending_embeddings()
    click.echo("Backfill complete:")
    click.echo(f"embedded: {embedded}")
    click.echo(f"failed: {failed}")
    click.echo(f"remaining: {remaining}")
    if failed:
        raise SystemExit(1)


@embeddings.command("similar")
@click.option("--title", required=True, help="Hypothetical ticket title.")
@click.option(
    "--description", required=True, help="Hypothetical ticket description."
)
@click.option(
    "--limit",
    type=click.IntRange(min=1, max=20),
    default=5,
    show_default=True,
    help="How many tickets to return (max 20).",
)
@with_appcontext
def embeddings_similar(title, description, limit):
    """Rank stored tickets by semantic similarity (cosine, pgvector).

    Reuses the exact same text builder, provider and repository search
    the future classification flow will use — the CLI demonstrates the
    real pipeline, not a parallel implementation. No HTTP endpoint yet;
    no duplicate/match decisions, only a ranking with similarity scores.
    """
    from app.embeddings import EmbeddingError
    from app.errors import ApiError
    from app.services import embedding_service

    try:
        results = embedding_service.find_similar_tickets(
            title=title, description=description, limit=limit
        )
    except ApiError as exc:
        raise click.ClickException(str(exc)) from exc
    except EmbeddingError as exc:
        raise click.ClickException(
            f"embedding failed: {exc.message} ({exc.kind})"
        ) from exc

    if not results:
        click.echo(
            "No similar tickets found (try 'flask embeddings backfill')."
        )
        return

    click.echo(f"Most similar tickets ({len(results)}):")
    for ticket, similarity in results:
        click.echo(
            f"  {similarity:.4f}  {ticket.ticket_number}  "
            f"[{ticket.status.value}]  {ticket.title}"
        )
