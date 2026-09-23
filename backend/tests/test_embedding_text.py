"""build_ticket_embedding_text: the canonical, deterministic ticket text."""

import inspect

from app.embeddings.text import build_ticket_embedding_text


def test_format_is_exact_and_deterministic():
    args = ("Cannot print", "The printer is offline.")
    assert build_ticket_embedding_text(*args) == (
        "Title: Cannot print\nDescription: The printer is offline."
    )
    # Same inputs always produce the same text (re-embeds are reproducible).
    assert build_ticket_embedding_text(*args) == build_ticket_embedding_text(*args)


def test_strips_surrounding_whitespace():
    text = build_ticket_embedding_text(
        "  Cannot sync mail  ", "  Errors on startup. "
    )
    assert text == "Title: Cannot sync mail\nDescription: Errors on startup."


def test_never_sees_anything_beyond_title_and_description():
    # The signature is the guarantee: category (the label a future
    # classifier must predict), status, priority, assignee and requester
    # cannot leak into the embedded text.
    assert list(inspect.signature(build_ticket_embedding_text).parameters) == [
        "title",
        "description",
    ]
    assert (
        build_ticket_embedding_text("Network down", "VPN times out")
        == "Title: Network down\nDescription: VPN times out"
    )
