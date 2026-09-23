"""Leave-one-out evaluation of the weighted-vote classifier.

Tiny on purpose: no ML tooling, no external service, nothing to pay
(USD 0). Each demo ticket is classified from the other demo tickets
(self excluded, evidence rules identical to production) and compared
with its known category.

Honesty rules baked into the report: the embedding provider is always
named, and with FakeEmbeddingProvider the output states loudly that it
validates the evaluation MECHANICS ONLY — hash vectors carry no meaning,
so those numbers say nothing about semantic quality. There is no target
accuracy or abstention rate anywhere: thresholds are hypotheses, results
are published exactly as measured.

The evaluation is read-only: unlike ticket creation, it never writes
AI_CLASSIFIED events or touches categories.
"""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app

from app.errors import ValidationError
from app.evaluation.dataset import (
    DEMO_CATEGORY_SLUGS,
    DEMO_TICKETS,
    REQUESTER_EMAIL,
)
from app.extensions import db
from app.models import Ticket, TicketPriority
from app.repositories.category_repository import CategoryRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository
from app.services.classification_service import decide, load_neighbor_votes

_ticket_repo = TicketRepository()

ABSTAIN_LABEL = "<abstain>"
_FAKE_PROVIDER = "fake"


def ensure_dataset() -> tuple[int, int]:
    """Insert the demo tickets that are missing. Idempotent, one txn.

    Matched by exact title, so no schema marker is needed. Requires the
    reference data from ``flask seed`` (categories + requester). Returns
    ``(created this run, present afterwards)``.
    """
    missing_categories = [
        slug
        for slug in DEMO_CATEGORY_SLUGS
        if CategoryRepository().get_by_slug(slug) is None
    ]
    if missing_categories:
        raise ValidationError(
            "missing categories: "
            f"{', '.join(missing_categories)} — run 'flask seed' first"
        )
    requester = UserRepository().get_by_email(REQUESTER_EMAIL)
    if requester is None:
        raise ValidationError(
            f"missing requester {REQUESTER_EMAIL} — run 'flask seed' first"
        )

    categories = {
        slug: CategoryRepository().get_by_slug(slug) for slug in DEMO_CATEGORY_SLUGS
    }
    titles = [title for title, _, _ in DEMO_TICKETS]
    present_titles = {ticket.title for ticket in _ticket_repo.list_by_titles(titles)}

    created = 0
    for title, description, slug in DEMO_TICKETS:
        if title in present_titles:
            continue
        db.session.add(
            Ticket(
                title=title,
                description=description,
                requester=requester,
                category=categories[slug],
                priority=TicketPriority.MEDIUM,
            )
        )
        created += 1
    db.session.commit()
    return created, len(DEMO_TICKETS)


@dataclass(frozen=True)
class EvalResult:
    """One leave-one-out verdict."""

    truth: str            # known category slug
    predicted: str | None # classifier answer, None when it abstained
    reason: str           # outcome reason (why it abstained, or CLASSIFIED)
    confidence: float     # reported confidence (0.0 when abstained)
    forced: str | None    # same vote with every gate wide open


@dataclass(frozen=True)
class EvaluationReport:
    """Aggregated leave-one-out results plus the honest metrics."""

    provider: str
    k: int
    thresholds: tuple[float, float, float]  # (similarity, margin, confidence)
    results: tuple[EvalResult, ...]

    # --- counts ----------------------------------------------------------

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def classified(self) -> int:
        return sum(1 for item in self.results if item.predicted is not None)

    @property
    def abstained(self) -> int:
        return self.total - self.classified

    @property
    def correct(self) -> int:
        return sum(
            1 for item in self.results if item.predicted == item.truth
        )

    @property
    def forced_correct(self) -> int:
        return sum(1 for item in self.results if item.forced == item.truth)

    # --- metrics (None means "not computable" and prints as n/a) --------

    @property
    def coverage(self) -> float:
        return self.classified / self.total if self.total else 0.0

    @property
    def abstention_rate(self) -> float:
        return self.abstained / self.total if self.total else 0.0

    @property
    def accuracy_among_classified(self) -> float | None:
        if not self.classified:
            return None
        return self.correct / self.classified

    @property
    def accuracy_overall(self) -> float:
        """Abstentions count as misses: the end-to-end honest number."""
        return self.correct / self.total if self.total else 0.0

    @property
    def forced_accuracy(self) -> float:
        """Accuracy if the classifier were forced to always answer."""
        return self.forced_correct / self.total if self.total else 0.0

    @property
    def confidence_mean(self) -> float | None:
        return _mean(
            item.confidence for item in self.results if item.predicted
        )

    @property
    def confidence_correct(self) -> float | None:
        """Mean confidence of correct calls — should sit above wrong."""
        return _mean(
            item.confidence
            for item in self.results
            if item.predicted is not None and item.predicted == item.truth
        )

    @property
    def confidence_wrong(self) -> float | None:
        return _mean(
            item.confidence
            for item in self.results
            if item.predicted is not None and item.predicted != item.truth
        )

    @property
    def abstained_by_reason(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.results:
            if item.predicted is None:
                counts[item.reason] = counts.get(item.reason, 0) + 1
        return counts

    @property
    def confusion(self) -> dict[tuple[str, str], int]:
        """(truth, prediction) counts; abstentions land in <abstain>."""
        counts: dict[tuple[str, str], int] = {}
        for item in self.results:
            key = (item.truth, item.predicted or ABSTAIN_LABEL)
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def truth_labels(self) -> list[str]:
        return sorted({item.truth for item in self.results})

    @property
    def predicted_labels(self) -> list[str]:
        return sorted(
            {item.predicted or ABSTAIN_LABEL for item in self.results}
        )


def _mean(values) -> float | None:
    values = list(values)
    if not values:
        return None
    return sum(values) / len(values)


def evaluate(
    *,
    k: int,
    min_similarity: float,
    min_margin: float,
    min_confidence: float,
) -> EvaluationReport:
    """Leave-one-out: classify each demo ticket from the other ones.

    Reuses the production evidence loader and the pure vote — same
    filters, same query, same gates — so the report measures the real
    classifier, not a parallel implementation. Read-only: no event is
    written and no category changes. ``CLASSIFICATION_ENABLED`` does not
    gate this explicit analysis tool (it exists precisely to study
    settings); it only gates automatic classification on ticket flow.
    """
    titles = [title for title, _, _ in DEMO_TICKETS]
    rows = [row for row in _ticket_repo.list_by_titles(titles)
            if row.category_id is not None]
    if len(rows) < len(DEMO_TICKETS):
        raise ValidationError(
            f"only {len(rows)}/{len(DEMO_TICKETS)} demo tickets present "
            "with a category — run 'flask classification evaluate' again"
        )
    pending = [row for row in rows if row.embedding is None]
    if pending:
        raise ValidationError(
            f"{len(pending)} demo tickets have no embedding yet — "
            "run 'flask embeddings backfill' first"
        )

    results: list[EvalResult] = []
    for ticket in rows:
        truth = ticket.category.slug
        neighbors = load_neighbor_votes(ticket, k=k)
        outcome = decide(
            neighbors,
            k=k,
            min_similarity=min_similarity,
            min_margin=min_margin,
            min_confidence=min_confidence,
        )
        # Same vote with every gate wide open: what the strategy would
        # have answered if forced (still None with zero usable evidence).
        forced = decide(
            neighbors,
            k=k,
            min_similarity=0.0,
            min_margin=0.0,
            min_confidence=0.0,
        )
        results.append(
            EvalResult(
                truth=truth,
                predicted=outcome.category_slug if outcome.classified else None,
                reason=outcome.reason,
                confidence=outcome.confidence,
                forced=forced.category_slug if forced.classified else None,
            )
        )

    return EvaluationReport(
        provider=current_app.config["EMBEDDING_PROVIDER"],
        k=k,
        thresholds=(min_similarity, min_margin, min_confidence),
        results=tuple(results),
    )


def format_report(report: EvaluationReport) -> list[str]:
    """Plain-text metrics table: stdlib only, no external tooling.

    Deliberately reports without judging: no pass/fail line, no target —
    numbers for the record, provider named, caveats stated.
    """
    r = report
    min_similarity, min_margin, min_confidence = r.thresholds
    lines = [
        "SupportIQ classifier evaluation - leave-one-out",
        f"dataset:    {r.total} fictional tickets / "
        f"{len(r.truth_labels)} categories",
        f"provider:   {r.provider}",
        f"K:          {r.k}",
        f"thresholds: min_similarity={min_similarity} "
        f"min_margin={min_margin} min_confidence={min_confidence}",
    ]
    if r.provider == _FAKE_PROVIDER:
        lines += [
            "!! FakeEmbeddingProvider in use: these numbers validate the",
            "!! evaluation MECHANICS ONLY. Fake vectors carry no semantic",
            "!! meaning, so the accuracies below say nothing about how",
            "!! well the classifier understands tickets. Re-run with the",
            "!! real free-tier provider for meaningful results.",
        ]
    lines += [
        "",
        f"coverage (classified):           {r.classified}/{r.total} "
        f"({r.coverage:.0%})",
        f"abstention rate:                 {r.abstained}/{r.total} "
        f"({r.abstention_rate:.0%})",
        f"accuracy among classified:       {_pct(r.accuracy_among_classified)}",
        f"overall accuracy (abstain=miss): {_pct(r.accuracy_overall)}",
        f"forced accuracy (gates off):     {_pct(r.forced_accuracy)}",
        f"confidence (correct):            {_num(r.confidence_correct)}",
        f"confidence (wrong):              {_num(r.confidence_wrong)}",
        f"confidence (mean):               {_num(r.confidence_mean)}",
    ]
    if r.abstained:
        reasons = ", ".join(
            f"{name}={count}"
            for name, count in sorted(r.abstained_by_reason.items())
        )
        lines.append(f"abstained by reason:             {reasons}")

    lines += _confusion_lines(r)
    return lines


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _confusion_lines(r: EvaluationReport) -> list[str]:
    width = 11
    labels = r.predicted_labels
    lines = [
        "",
        "confusion matrix (rows = true category, cols = prediction):",
        " " * 16 + "".join(label.rjust(width) for label in labels),
    ]
    for truth in r.truth_labels:
        cells = "".join(
            str(r.confusion.get((truth, label), 0)).rjust(width)
            for label in labels
        )
        lines.append(truth.ljust(16) + cells)
    return lines
