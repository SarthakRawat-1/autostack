# File: services/checkpointer.py
"""
Shared PostgresSaver checkpointer for LangGraph workflows.

Replaces MemorySaver so that workflow checkpoints are persisted in
PostgreSQL and survive process restarts, enabling proper HITL resume.

Uses a ConnectionPool (not a single connection) so that concurrent
async workflows don't collide on the same psycopg connection.
"""

import logging
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from api.config import settings

logger = logging.getLogger(__name__)

_checkpointer: PostgresSaver | None = None
_pool: ConnectionPool | None = None


def get_checkpointer() -> PostgresSaver:
    """
    Return a singleton PostgresSaver backed by a connection pool.

    Uses ``psycopg_pool.ConnectionPool`` (min 2, max 10) so concurrent
    ``ainvoke()`` calls each acquire their own connection.  LangGraph
    wraps the sync checkpointer in ``run_in_executor`` for async code.

    On first call the checkpoint tables are created via ``setup()``.
    """
    global _checkpointer, _pool
    if _checkpointer is not None:
        return _checkpointer

    conn_string = settings.database_url
    # psycopg3 requires postgresql:// not postgres://
    if conn_string.startswith("postgres://"):
        conn_string = conn_string.replace("postgres://", "postgresql://", 1)

    logger.info("Initializing PostgresSaver checkpointer with connection pool")
    _pool = ConnectionPool(
        conninfo=conn_string,
        min_size=2,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    _checkpointer = PostgresSaver(conn=_pool)
    _checkpointer.setup()
    logger.info("PostgresSaver checkpointer ready (pool: min=2, max=10)")
    return _checkpointer
