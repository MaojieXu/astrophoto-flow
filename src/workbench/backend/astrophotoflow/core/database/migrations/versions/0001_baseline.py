"""Platform schema baseline.

No domain tables exist yet: assets, datasets and equipment receipts arrive with
their own migrations, not as speculative tables in this one.
"""

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
