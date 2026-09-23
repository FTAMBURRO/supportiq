"""semantic foundation: pgvector extension + ticket embedding columns

Revision ID: c94d2e81fa63
Revises: a6fa2ebf0568
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'c94d2e81fa63'
down_revision = 'a6fa2ebf0568'
branch_labels = None
depends_on = None


def upgrade():
    # The extension must exist before any VECTOR type is referenced.
    # Runs as the connecting (superuser) user; idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Nullable by design: a ticket without embedding is a valid state
    # ("pending / to be backfilled"), never a corrupt one.
    op.add_column('tickets', sa.Column('embedding', Vector(768), nullable=True))
    op.add_column(
        'tickets',
        sa.Column('embedding_model', sa.String(length=64), nullable=True),
    )
    # No ANN index (HNSW/IVFFlat): exact search is enough for now.


def downgrade():
    op.drop_column('tickets', 'embedding_model')
    op.drop_column('tickets', 'embedding')
    # The vector extension is intentionally NOT dropped: removing it would
    # be irreversible for any stored embeddings and it is part of the
    # infrastructure now. Drop it manually only if abandoning pgvector.
