"""Database initialization and persistence layer."""

from wine_agent.db.engine import (
    create_db_engine,
    get_database_url,
    get_engine,
    get_session,
    get_session_factory,
    init_db,
    reset_engine,
)
from wine_agent.db.models import (
    AIConversionRunDB,
    Base,
    InboxItemDB,
    RevisionDB,
    TastingNoteDB,
)
from wine_agent.db.repositories import (
    AIConversionRepository,
    InboxRepository,
    RevisionRepository,
    TastingNoteRepository,
)

__all__ = [
    # Engine
    "create_db_engine",
    "get_database_url",
    "get_engine",
    "get_session",
    "get_session_factory",
    "init_db",
    "reset_engine",
    # Models
    "Base",
    "InboxItemDB",
    "TastingNoteDB",
    "AIConversionRunDB",
    "RevisionDB",
    # Repositories
    "InboxRepository",
    "TastingNoteRepository",
    "AIConversionRepository",
    "RevisionRepository",
]
