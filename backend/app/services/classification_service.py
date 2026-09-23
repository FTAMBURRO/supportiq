"""Automatic category classification (Fase 3 · Milestone 2).

Strategy: similarity-weighted voting over the K closest historically
classified tickets retrieved with pgvector's exact cosine distance.

    S(c) = sum of max(similarity, 0) over neighbours carrying category c
    winner = argmax S(c)          share = S(winner) / total
    margin = (first - second) / total
    confidence = share * top_similarity

``confidence`` is a heuristic score in (0..1], NOT a calibrated
probability: it answers "how dominant is the winning category among
the retrieved evidence, scaled by the best match" — nothing statistical.
Calibration would need labelled outcomes that do not exist yet.

Abstention is a feature, not a failure: when evidence is weak or
divided the classifier returns an explicit reason instead of forcing a
prediction. The three gates (minimum top similarity, minimum margin,
minimum confidence) are configuration hypotheses validated with
``flask classification evaluate`` — deliberately never tuned toward a
target accuracy number.

Contract: classification is a product improvement, never a dependency.
``classify_and_persist`` never raises — no evidence, pgvector trouble
or any unexpected error leaves the ticket exactly as it was, so ticket
creation can never fail because of classification. It reuses the
embedding the ticket already has: zero embedding-provider calls.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable

from flask import current_app

from app.extensions import db
from app.models import CategorySource, Ticket, TicketEvent, TicketEventType
from app.repositories.ticket_repository import TicketRepository

_ticket_repo = TicketRepository()

# Outcome reasons (log + evaluation vocabulary; never stored as events
# unless a category was actually assigned).
REASON_CLASSIFIED = "CLASSIFIED"
REASON_DISABLED = "DISABLED"
REASON_ALREADY_CATEGORIZED = "ALREADY_CATEGORIZED"
REASON_NO_EMBEDDING = "NO_EMBEDDING"
REASON_NO_EVIDENCE = "NO_EVIDENCE"
REASON_LOW_SIMILARITY = "LOW_SIMILARITY"
REASON_AMBIGUOUS = "AMBIGUOUS"
REASON_LOW_CONFIDENCE = "LOW_CONFIDENCE"
REASON_FAILED = "FAILED"

# Top evidence kept in the AI_CLASSIFIED event: enough to explain the
# vote, small enough to never bloat the audit trail. Vectors are never
# serialized anywhere.
EVIDENCE_LIMIT = 3

# Reported values are rounded for stable output; the abstention gates
# are evaluated on the raw computation (thresholds have <= 4 decimals,
# so rounding after a passed gate can never push it below its limit).
_REPORT_DECIMALS = 4


@dataclass(frozen=True)
class NeighborVote:
    """One retrieved neighbour, ready to vote."""

    ticket_id: uuid.UUID
    ticket_number: str
    category_id: uuid.UUID
    category_slug: str
    similarity: float

    @property
    def weight(self) -> float:
        """Voting weight: a non-positive cosine similarity is not
        evidence and can only subtract, so it counts as zero."""
        return max(self.similarity, 0.0)


@dataclass(frozen=True)
class ClassificationOutcome:
    """Result of a classification attempt (classified or abstained)."""

    reason: str
    category_id: uuid.UUID | None = None
    category_slug: str | None = None
    confidence: float = 0.0
    share: float = 0.0
    margin: float = 0.0
    top_similarity: float = 0.0
    neighbors_used: int = 0
    evidence: tuple[NeighborVote, ...] = field(default_factory=tuple)

    @property
    def classified(self) -> bool:
        return self.reason == REASON_CLASSIFIED


def decide(
    neighbors: Iterable[NeighborVote],
    *,
    k: int,
    min_similarity: float,
    min_margin: float,
    min_confidence: float,
) -> ClassificationOutcome:
    """Pure similarity-weighted vote. No I/O, no Flask, no database.

    1. Keep usable evidence (category present), best-first, at most ``k``.
    2. Weight each neighbour by ``max(similarity, 0)``.
    3. Winner = highest accumulated weight; ties break on best single
       weight then id (deterministic — ambiguous ties are normally
       caught by the margin gate before the tie-break matters).
    4. Gates in order: relevance (best match), decisiveness (margin over
       the runner-up), overall (confidence). Failing any gate abstains
       with an explicit reason instead of forcing a weak prediction.
    """
    usable = sorted(
        (vote for vote in neighbors if vote.category_id is not None),
        key=lambda vote: (-vote.similarity, str(vote.ticket_id)),
    )[: max(k, 0)]
    if not usable:
        return ClassificationOutcome(reason=REASON_NO_EVIDENCE)

    evidence = tuple(usable[:EVIDENCE_LIMIT])
    top_similarity = usable[0].similarity
    neighbors_used = len(usable)

    scores: dict[uuid.UUID, float] = {}
    best: dict[uuid.UUID, float] = {}
    for vote in usable:
        weight = vote.weight
        scores[vote.category_id] = scores.get(vote.category_id, 0.0) + weight
        best[vote.category_id] = max(best.get(vote.category_id, 0.0), weight)

    total = sum(scores.values())
    if total <= 0.0:
        # Every retrieved similarity was <= 0 (sorted, so the best is
        # too): nothing resembling evidence — same failure as a plainly
        # too-weak best match, without dividing by zero.
        return ClassificationOutcome(
            reason=REASON_LOW_SIMILARITY,
            top_similarity=round(top_similarity, _REPORT_DECIMALS),
            neighbors_used=neighbors_used,
            evidence=evidence,
        )

    winner_id, winner_weight = min(
        scores.items(),
        key=lambda item: (-item[1], -best[item[0]], str(item[0])),
    )
    runner_up_weight = max(
        (
            weight
            for category_id, weight in scores.items()
            if category_id != winner_id
        ),
        default=0.0,
    )

    share = winner_weight / total
    margin = (winner_weight - runner_up_weight) / total
    confidence = share * top_similarity
    winner_slug = next(
        vote.category_slug
        for vote in usable
        if vote.category_id == winner_id
    )

    fields = {
        "confidence": round(confidence, _REPORT_DECIMALS),
        "share": round(share, _REPORT_DECIMALS),
        "margin": round(margin, _REPORT_DECIMALS),
        "top_similarity": round(top_similarity, _REPORT_DECIMALS),
        "neighbors_used": neighbors_used,
        "evidence": evidence,
    }

    if top_similarity < min_similarity:
        return ClassificationOutcome(reason=REASON_LOW_SIMILARITY, **fields)
    if margin < min_margin:
        return ClassificationOutcome(reason=REASON_AMBIGUOUS, **fields)
    if confidence < min_confidence:
        return ClassificationOutcome(reason=REASON_LOW_CONFIDENCE, **fields)
    return ClassificationOutcome(
        reason=REASON_CLASSIFIED,
        category_id=winner_id,
        category_slug=winner_slug,
        **fields,
    )


def load_neighbor_votes(ticket: Ticket, *, k: int) -> list[NeighborVote]:
    """Load classification evidence for a ticket (the I/O seam).

    Public because ``flask classification evaluate`` reuses exactly
    this loader: one implementation of the evidence rules, no parallel
    query. Tests replace it with controlled neighbours.
    """
    rows = _ticket_repo.find_classification_neighbors(
        exclude_ticket_id=ticket.id,
        embedding=ticket.embedding,
        model=ticket.embedding_model,
        k=k,
    )
    return [
        NeighborVote(
            ticket_id=neighbor.id,
            ticket_number=neighbor.ticket_number,
            category_id=neighbor.category_id,
            category_slug=neighbor.category.slug,
            similarity=similarity,
        )
        for neighbor, similarity in rows
    ]


def classify_and_persist(ticket: Ticket) -> ClassificationOutcome:
    """Classify an already-committed ticket. Best-effort: never raises.

    Explicit guards (never inferred from the embedding provider name),
    then the pure vote over the ticket's persisted embedding, then one
    short commit carrying the category and its AI_CLASSIFIED event.
    Any failure rolls back only this step and leaves the ticket as it
    was — the valid degraded state is "ticket exists, unclassified".
    """
    try:
        return _classify(ticket)
    except Exception:  # contract: creation never fails because of us
        db.session.rollback()
        current_app.logger.exception(
            "classification failed for %s; ticket left unchanged",
            ticket.ticket_number,
        )
        return ClassificationOutcome(reason=REASON_FAILED)


def _classify(ticket: Ticket) -> ClassificationOutcome:
    config = current_app.config

    if not config["CLASSIFICATION_ENABLED"]:
        return ClassificationOutcome(reason=REASON_DISABLED)
    if ticket.category_id is not None:
        # Never overwrite a category a human already provided.
        return ClassificationOutcome(reason=REASON_ALREADY_CATEGORIZED)
    if ticket.embedding is None or ticket.embedding_model is None:
        # No query vector (provider down / pending backfill). Backfill
        # embeds but deliberately does not classify: classification
        # happens at creation time only.
        return ClassificationOutcome(reason=REASON_NO_EMBEDDING)

    k = config["CLASSIFICATION_K"]
    outcome = decide(
        load_neighbor_votes(ticket, k=k),
        k=k,
        min_similarity=config["CLASSIFICATION_MIN_SIMILARITY"],
        min_margin=config["CLASSIFICATION_MIN_MARGIN"],
        min_confidence=config["CLASSIFICATION_MIN_CONFIDENCE"],
    )

    if not outcome.classified:
        # Abstention: no event, no state change, just a trace.
        current_app.logger.info(
            "classification of %s abstained: %s (%s usable neighbours)",
            ticket.ticket_number,
            outcome.reason,
            outcome.neighbors_used,
        )
        return outcome

    _persist_classification(ticket, outcome, k=k)
    current_app.logger.info(
        "classification: %s -> %s (confidence %.4f, %s neighbours)",
        ticket.ticket_number,
        outcome.category_slug,
        outcome.confidence,
        outcome.neighbors_used,
    )
    return outcome


def _persist_classification(
    ticket: Ticket, outcome: ClassificationOutcome, *, k: int
) -> None:
    """Assign category + audit event in one short transaction.

    The service owns the commit. No network call happens inside it: the
    query already ran and the vote is pure arithmetic.
    """
    event = TicketEvent(
        ticket=ticket,
        actor_id=None,  # system-generated, pre-auth (like PATCH events)
        event_type=TicketEventType.AI_CLASSIFIED,
        data={
            "category_id": str(outcome.category_id),
            "category_slug": outcome.category_slug,
            "confidence": outcome.confidence,
            "share": outcome.share,
            "margin": outcome.margin,
            "top_similarity": outcome.top_similarity,
            "k": k,
            "neighbors_used": outcome.neighbors_used,
            # Fixed-size evidence (top 3): enough to reconstruct the
            # vote by hand. Never vectors.
            "evidence": [
                {
                    "ticket_number": vote.ticket_number,
                    "category_slug": vote.category_slug,
                    "similarity": round(vote.similarity, _REPORT_DECIMALS),
                }
                for vote in outcome.evidence
            ],
        },
    )
    ticket.category_id = outcome.category_id
    ticket.category_source = CategorySource.AI
    ticket.classification_confidence = outcome.confidence
    _ticket_repo.add_event(event)
    db.session.commit()
