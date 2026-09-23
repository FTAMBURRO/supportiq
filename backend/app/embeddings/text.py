"""Deterministic ticket text for embeddings.

The embedding represents the semantic content of the reported problem
only: never category, status, priority, assignee or requester.
Embedding the category would leak the label a future classifier has to
predict, inflating its results and shifting the text distribution
between stored tickets (which may have a category) and new queries
(which never do).
"""


def build_ticket_embedding_text(title: str, description: str) -> str:
    """Return the canonical text to embed for a ticket.

    Pure and deterministic: the same inputs always produce the same
    string, so re-embedding is reproducible. Accepts plain strings (not
    a Ticket) because the semantic-search CLI embeds a hypothetical
    ticket that does not exist yet.
    """
    return f"Title: {title.strip()}\nDescription: {description.strip()}"
