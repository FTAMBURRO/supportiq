"""Pure weighted-vote strategy: no database, no Flask, no vectors.

Every number here is hand-computable, so the assertions pin the exact
formula (weights, share, margin, confidence) and every abstention gate
with its reason. The PostgreSQL-only vector query is covered separately
by test_classification_pg.py.
"""

import uuid

import pytest

from app.services import classification_service as cs

# Same defaults as Config (passed explicitly: decide() reads nothing).
K = 5
MIN_SIMILARITY = 0.55
MIN_MARGIN = 0.20
MIN_CONFIDENCE = 0.50

GATES = dict(
    k=K,
    min_similarity=MIN_SIMILARITY,
    min_margin=MIN_MARGIN,
    min_confidence=MIN_CONFIDENCE,
)

# Category ids are stable within a test so same-category votes accumulate.
_CATEGORIES = {
    slug: uuid.uuid4()
    for slug in ("network", "access", "hardware", "software", "billing")
}


def vote(similarity, slug, number="SUP-000001", category_id=None):
    return cs.NeighborVote(
        ticket_id=uuid.uuid4(),
        ticket_number=number,
        category_id=_CATEGORIES[slug] if category_id is None else category_id,
        category_slug=slug,
        similarity=similarity,
    )


def test_no_neighbours_means_no_evidence():
    outcome = cs.decide([], **GATES)

    assert outcome.reason == cs.REASON_NO_EVIDENCE
    assert not outcome.classified
    assert outcome.category_id is None
    assert outcome.neighbors_used == 0
    assert outcome.evidence == ()


def test_similarity_weighted_vote_picks_the_dominant_category():
    # The approved design example: Network at 0.94/0.91/0.84 vs Access
    # at 0.58 -> Network weights 2.69 of a 3.27 total.
    outcome = cs.decide(
        [
            vote(0.94, "network", "SUP-001"),
            vote(0.91, "network", "SUP-014"),
            vote(0.84, "network", "SUP-032"),
            vote(0.58, "access", "SUP-040"),
        ],
        **GATES,
    )

    assert outcome.classified
    assert outcome.reason == cs.REASON_CLASSIFIED
    assert outcome.category_id == _CATEGORIES["network"]
    assert outcome.category_slug == "network"
    assert outcome.share == pytest.approx(2.69 / 3.27, abs=1e-4)  # 0.8226
    assert outcome.margin == pytest.approx(2.11 / 3.27, abs=1e-4)  # 0.6453
    assert outcome.top_similarity == 0.94
    # confidence = share * top_similarity = 0.8226 * 0.94 ~ 0.7733
    assert outcome.confidence == pytest.approx(0.8226 * 0.94, abs=1e-4)
    assert outcome.neighbors_used == 4
    # Audit evidence is capped at the top 3, best match first.
    assert len(outcome.evidence) == cs.EVIDENCE_LIMIT == 3
    assert [v.similarity for v in outcome.evidence] == [0.94, 0.91, 0.84]


def test_single_strong_neighbour_classifies_with_full_margin():
    outcome = cs.decide([vote(0.92, "hardware")], **GATES)

    assert outcome.classified
    assert outcome.category_slug == "hardware"
    assert outcome.share == pytest.approx(1.0)
    assert outcome.margin == pytest.approx(1.0)  # no runner-up
    assert outcome.confidence == pytest.approx(0.92)
    assert outcome.neighbors_used == 1


def test_weak_best_match_abstains_relevance_gate():
    # The "coffee machine exploded" shape: everything far below the gate.
    outcome = cs.decide(
        [vote(0.31, "network"), vote(0.29, "billing"), vote(0.27, "access")],
        **GATES,
    )

    assert not outcome.classified
    assert outcome.reason == cs.REASON_LOW_SIMILARITY
    assert outcome.category_id is None
    assert outcome.top_similarity == 0.31


def test_two_strong_rivals_abstain_as_ambiguous():
    # Both above the relevance gate, but neck-and-neck: margin 0.029 < 0.20.
    outcome = cs.decide([vote(0.90, "network"), vote(0.85, "billing")], **GATES)

    assert not outcome.classified
    assert outcome.reason == cs.REASON_AMBIGUOUS
    assert outcome.margin == pytest.approx(0.05 / 1.75, abs=1e-4)


def test_decisive_but_unimpressive_evidence_abstains_confidence_gate():
    # Relevance (0.60 >= 0.55) and margin (0.30 >= 0.20) pass, yet
    # confidence = 0.60 share * 0.60 top = 0.36 < 0.50 -> abstain.
    outcome = cs.decide(
        [vote(0.60, "network"), vote(0.30, "hardware"), vote(0.10, "software")],
        **GATES,
    )

    assert not outcome.classified
    assert outcome.reason == cs.REASON_LOW_CONFIDENCE
    assert outcome.confidence == pytest.approx(0.36)
    assert outcome.share == pytest.approx(0.60)
    assert outcome.margin == pytest.approx(0.30)


def test_exact_tie_abstains_instead_of_coin_flipping():
    outcome = cs.decide([vote(0.70, "network"), vote(0.70, "access")], **GATES)

    assert not outcome.classified
    assert outcome.reason == cs.REASON_AMBIGUOUS
    assert outcome.margin == pytest.approx(0.0)
    assert outcome.category_id is None


def test_negative_similarity_contributes_zero_weight():
    outcome = cs.decide(
        [vote(0.85, "network"), vote(-0.40, "access")], **GATES
    )

    assert outcome.classified
    assert outcome.category_slug == "network"
    assert outcome.share == pytest.approx(1.0)  # 0.85 / (0.85 + 0)
    assert outcome.neighbors_used == 2  # still counted as retrieved


def test_all_nonpositive_similarities_abstain_without_dividing_by_zero():
    outcome = cs.decide([vote(-0.20, "network"), vote(-0.10, "access")], **GATES)

    assert not outcome.classified
    assert outcome.reason == cs.REASON_LOW_SIMILARITY
    assert outcome.top_similarity == pytest.approx(-0.10)  # best of the bad


def test_neighbours_without_a_category_never_vote():
    no_category = cs.NeighborVote(
        ticket_id=uuid.uuid4(),
        ticket_number="SUP-000009",
        category_id=None,  # type: ignore[arg-type]  (the case under test)
        category_slug="",
        similarity=0.99,
    )

    outcome = cs.decide(
        [no_category, vote(0.60, "hardware", "SUP-000002")], **GATES
    )
    assert outcome.classified
    assert outcome.category_slug == "hardware"
    assert outcome.neighbors_used == 1  # the uncategorized row did not count

    only_uncategorized = cs.decide([no_category], **GATES)
    assert only_uncategorized.reason == cs.REASON_NO_EVIDENCE


def test_k_limits_who_votes_and_evidence_stays_capped():
    # 7 candidates, K=5: the two weakest fall out of the vote entirely.
    outcome = cs.decide(
        [
            vote(0.90, "network", "SUP-1"),
            vote(0.88, "network", "SUP-2"),
            vote(0.86, "network", "SUP-3"),
            vote(0.84, "network", "SUP-4"),
            vote(0.82, "billing", "SUP-5"),
            vote(0.80, "billing", "SUP-6"),
            vote(0.78, "billing", "SUP-7"),
        ],
        **GATES,
    )

    assert outcome.classified
    assert outcome.category_slug == "network"
    assert outcome.neighbors_used == 5
    assert len(outcome.evidence) == 3


def test_input_order_does_not_change_the_decision():
    votes = [
        vote(0.94, "network", "SUP-1"),
        vote(0.60, "billing", "SUP-2"),
        vote(0.91, "network", "SUP-3"),
    ]
    forward = cs.decide(votes, **GATES)
    backward = cs.decide(list(reversed(votes)), **GATES)

    assert forward == backward
