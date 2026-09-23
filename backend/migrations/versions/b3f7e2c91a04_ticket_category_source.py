"""classification provenance: category_source + classification_confidence

Revision ID: b3f7e2c91a04
Revises: c94d2e81fa63
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b3f7e2c91a04'
down_revision = 'c94d2e81fa63'
branch_labels = None
depends_on = None


def upgrade():
    # Who assigned the CURRENT category. This is also the classifier's
    # feedback-loop guard: only MANUAL categories count as evidence.
    # The server default backfills existing rows as human-assigned,
    # which is accurate — no AI classification exists yet.
    op.add_column(
        'tickets',
        sa.Column(
            'category_source',
            sa.String(length=6),
            server_default='MANUAL',
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'ticket_category_source',
        'tickets',
        "category_source IN ('MANUAL', 'AI')",
    )

    # Heuristic score (0..1, not a calibrated probability) of the last
    # AI classification. NULL means "category not set by the AI".
    op.add_column(
        'tickets',
        sa.Column('classification_confidence', sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        'ticket_classification_confidence',
        'tickets',
        'classification_confidence >= 0 AND classification_confidence <= 1',
    )


def downgrade():
    op.drop_constraint(
        'ticket_classification_confidence', 'tickets', type_='check'
    )
    op.drop_column('tickets', 'classification_confidence')
    op.drop_constraint('ticket_category_source', 'tickets', type_='check')
    op.drop_column('tickets', 'category_source')
