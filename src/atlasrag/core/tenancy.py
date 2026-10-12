"""Request-scoped workspace identity; internal workers deliberately run unscoped."""

from contextvars import ContextVar

workspace_id: ContextVar[str | None] = ContextVar("workspace_id", default=None)


def new_row_workspace() -> str:
    # Pre-isolation data is retained for an operator to assign, never made public.
    return workspace_id.get() or "legacy"
