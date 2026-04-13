"""Async SQLAlchemy engine and session factory — re-exported from documentlm_core."""

from documentlm_core.core.database import (  # noqa: F401
    Base,
    _get_engine,
    _get_session_factory,
    get_db,
)
