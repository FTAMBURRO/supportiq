"""baseline: empty schema

Revision ID: baseline01
Revises:
Create Date: 2026-09-22

Empty baseline revision. It exists so the migration chain can be applied
end-to-end before any domain models are introduced. It creates no tables.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "baseline01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """No-op: there is no schema yet."""
    pass


def downgrade():
    """No-op: nothing to remove."""
    pass
