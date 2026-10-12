"""The additive, version-checked workspace migration used by hosted cold starts."""

from typing import Any

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Connection


def add_workspace_columns(operations: Any) -> None:
    for table in ("documents", "messages"):
        operations.add_column(
            table, sa.Column("workspace_id", sa.String(64), nullable=False, server_default="legacy")
        )
        operations.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])


def upgrade_hosted_workspace(connection: Connection) -> None:
    # This narrowly scoped additive release is safe beside the previous application.
    # Never run arbitrary future migrations or infer ownership for pre-existing rows.
    version = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    if version == "0002":
        return
    if connection.dialect.name == "postgresql":
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(746724901)"))
        version = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    if version == "0002":
        return
    if version != "0001":
        raise RuntimeError("Apply base database migrations before workspace isolation")
    add_workspace_columns(Operations(MigrationContext.configure(connection)))
    connection.execute(
        sa.text("UPDATE alembic_version SET version_num = '0002' WHERE version_num = '0001'")
    )
