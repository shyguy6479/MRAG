"""Isolate documents and conversations; preserve old data in a private legacy scope."""

from alembic import op

from atlasrag.core.schema import add_workspace_columns

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_workspace_columns(op)


def downgrade() -> None:
    for table in ("messages", "documents"):
        op.drop_index(f"ix_{table}_workspace_id", table_name=table)
        op.drop_column(table, "workspace_id")
