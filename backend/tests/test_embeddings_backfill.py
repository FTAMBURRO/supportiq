"""``flask embeddings backfill``: pending-only, bounded, idempotent, resilient."""

from app.embeddings import EmbeddingError, EmbeddingErrorKind
from app.models import Ticket
from app.services import embedding_service


def _create_pending(app, client, ticket_payload, count):
    """Create `count` tickets while the provider is down → embedding NULL."""
    app.config["EMBEDDING_PROVIDER"] = "gemini"
    app.config["EMBEDDING_API_KEY"] = ""
    for index in range(count):
        payload = dict(ticket_payload, title=f"Pending ticket {index}")
        response = client.post("/api/tickets", json=payload)
        assert response.status_code == 201
    app.config["EMBEDDING_PROVIDER"] = "fake"


def _vectors(db):
    return {
        ticket.id: list(ticket.embedding)
        for ticket in db.session.query(Ticket).all()
    }


def test_backfill_respects_limit_runs_only_pending_and_is_idempotent(
    app, client, db, ticket_payload
):
    _create_pending(app, client, ticket_payload, 3)
    runner = app.test_cli_runner()

    first = runner.invoke(args=["embeddings", "backfill", "--limit", "2"])
    assert first.exit_code == 0
    assert "embedded: 2" in first.output
    assert "failed: 0" in first.output
    assert "remaining: 1" in first.output

    second = runner.invoke(args=["embeddings", "backfill"])
    assert second.exit_code == 0
    assert "embedded: 1" in second.output
    assert "remaining: 0" in second.output
    assert all(vector is not None for vector in _vectors(db).values())

    snapshot = _vectors(db)
    third = runner.invoke(args=["embeddings", "backfill"])
    assert third.exit_code == 0
    assert "embedded: 0" in third.output  # nothing pending → zero calls
    assert "remaining: 0" in third.output
    assert _vectors(db) == snapshot  # re-running changed nothing


def test_backfill_survives_individual_failure_and_recovers_later(
    app, client, db, ticket_payload, monkeypatch
):
    _create_pending(app, client, ticket_payload, 3)

    real_get_provider = embedding_service.get_provider

    class FailFirstCall:
        calls = 0

        def embed(self, text):
            FailFirstCall.calls += 1
            if FailFirstCall.calls == 1:
                raise EmbeddingError(
                    "simulated provider outage",
                    kind=EmbeddingErrorKind.NETWORK,
                )
            return real_get_provider().embed(text)

    monkeypatch.setattr(
        embedding_service, "get_provider", lambda: FailFirstCall()
    )
    runner = app.test_cli_runner()

    first = runner.invoke(args=["embeddings", "backfill"])
    assert first.exit_code == 1  # failure is reported in the exit code...
    assert "embedded: 2" in first.output  # ...but the rest kept going
    assert "failed: 1" in first.output
    assert "remaining: 1" in first.output

    monkeypatch.undo()  # provider healthy again
    second = runner.invoke(args=["embeddings", "backfill"])
    assert second.exit_code == 0
    assert "embedded: 1" in second.output  # the failed ticket is retried
    assert "remaining: 0" in second.output
