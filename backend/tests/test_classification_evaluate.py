"""Fictional dataset integrity and leave-one-out evaluation.

Dataset/CLI checks run on the SQLite suite (they stop before any
pgvector operator); the full evaluation run against real cosine
neighbours is PostgreSQL-marked in test_classification_pg.py.
"""

import re
from collections import Counter

import pytest

from app.errors import ValidationError
from app.evaluation.dataset import (
    DEMO_CATEGORY_SLUGS,
    DEMO_TICKETS,
)
from app.services import evaluation_service as es

# The dataset must stay invented: these names may never appear.
_FORBIDDEN = re.compile(r"\b(uba|siu|mapuche)\b", re.IGNORECASE)


def test_dataset_is_36_unique_tickets_with_six_per_category():
    titles = [title for title, _, _ in DEMO_TICKETS]
    assert len(titles) == len(set(titles)) == 36
    assert all(len(title) <= 200 for title in titles)

    per_category = Counter(slug for _, _, slug in DEMO_TICKETS)
    assert set(per_category) == set(DEMO_CATEGORY_SLUGS)
    assert all(count == 6 for count in per_category.values())


def test_dataset_contains_no_real_world_names():
    corpus = " ".join(
        f"{title} {description}" for title, description, _ in DEMO_TICKETS
    )
    assert not _FORBIDDEN.search(corpus)


def test_report_metrics_are_computed_exactly_as_documented():
    report = es.EvaluationReport(
        provider="gemini-embedding-001",
        k=5,
        thresholds=(0.55, 0.20, 0.50),
        results=(
            es.EvalResult(
                truth="access", predicted="access",
                reason="CLASSIFIED", confidence=0.9, forced="access",
            ),
            es.EvalResult(  # wrong call: gates off yields the same winner
                truth="network", predicted="access",
                reason="CLASSIFIED", confidence=0.6, forced="access",
            ),
            es.EvalResult(  # abstained, though forced would have answered
                truth="billing", predicted=None,
                reason="LOW_SIMILARITY", confidence=0.0, forced="billing",
            ),
            es.EvalResult(  # abstained; forced tie-break guesses wrong
                truth="other", predicted=None,
                reason="AMBIGUOUS", confidence=0.0, forced="access",
            ),
        ),
    )

    assert (report.total, report.classified, report.abstained) == (4, 2, 2)
    assert report.correct == 1
    assert report.forced_correct == 2
    assert report.coverage == pytest.approx(0.5)
    assert report.abstention_rate == pytest.approx(0.5)
    assert report.accuracy_among_classified == pytest.approx(0.5)
    assert report.accuracy_overall == pytest.approx(0.25)  # abstain = miss
    assert report.forced_accuracy == pytest.approx(0.5)
    assert report.confidence_mean == pytest.approx(0.75)
    assert report.confidence_correct == pytest.approx(0.9)
    assert report.confidence_wrong == pytest.approx(0.6)
    assert report.abstained_by_reason == {"LOW_SIMILARITY": 1, "AMBIGUOUS": 1}
    assert report.confusion == {
        ("access", "access"): 1,
        ("network", "access"): 1,
        ("billing", "<abstain>"): 1,
        ("other", "<abstain>"): 1,
    }
    assert report.predicted_labels == ["<abstain>", "access"]


def test_format_names_the_fake_provider_and_disclaims_semantics():
    report = es.EvaluationReport(
        provider="fake",
        k=5,
        thresholds=(0.55, 0.20, 0.50),
        results=(
            es.EvalResult(
                truth="access", predicted=None,
                reason="NO_EVIDENCE", confidence=0.0, forced=None,
            ),
        ),
    )
    text = "\n".join(es.format_report(report))

    assert "FakeEmbeddingProvider" in text
    assert "MECHANICS ONLY" in text
    assert "provider:   fake" in text
    # Nothing classified -> the metric prints n/a instead of dividing.
    assert "accuracy among classified:       n/a" in text
    assert "confusion matrix" in text
    assert "forced accuracy (gates off):" in text


def test_format_of_a_real_provider_carries_no_fake_warning():
    report = es.EvaluationReport(
        provider="gemini-embedding-001",
        k=5,
        thresholds=(0.55, 0.20, 0.50),
        results=(),
    )
    text = "\n".join(es.format_report(report))

    assert "FakeEmbeddingProvider" not in text
    assert "provider:   gemini-embedding-001" in text


def test_ensure_dataset_is_idempotent(app, db):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0

    created, present = es.ensure_dataset()
    assert (created, present) == (36, 36)

    created_again, present_again = es.ensure_dataset()
    assert (created_again, present_again) == (0, 36)

    from app.models import Ticket

    tickets = db.session.query(Ticket).all()
    assert len(tickets) == 36
    # Ground truth is stored as human-assigned evidence.
    assert all(ticket.category is not None for ticket in tickets)
    assert all(ticket.category_source.value == "MANUAL" for ticket in tickets)


def test_evaluate_refuses_to_run_without_embeddings(app, db):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0
    es.ensure_dataset()

    with pytest.raises(ValidationError, match="flask embeddings backfill"):
        es.evaluate(
            k=5, min_similarity=0.55, min_margin=0.20, min_confidence=0.50
        )


def test_evaluate_cli_seeds_idempotently_and_demands_backfill(app, db):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0

    first = runner.invoke(args=["classification", "evaluate"])
    assert first.exit_code == 1  # no embeddings yet: actionable stop
    assert "dataset: 36 demo tickets present (36 created this run)." in (
        first.output
    )
    assert "backfill" in first.output

    second = runner.invoke(args=["classification", "evaluate"])
    assert second.exit_code == 1
    assert "(0 created this run)" in second.output
