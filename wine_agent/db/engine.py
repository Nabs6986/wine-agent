"""SQLite database engine and session management."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Default database path (can be overridden via environment variable)
DEFAULT_DB_PATH = Path.home() / ".wine_agent" / "wine_agent.db"


def get_database_url(db_path: Path | str | None = None) -> str:
    """
    Get the SQLite database URL.

    Args:
        db_path: Optional path to the database file. If None, uses
                 DATABASE_URL env var or default path.

    Returns:
        SQLite connection URL.
    """
    if db_path is not None:
        path = Path(db_path)
    elif os.environ.get("DATABASE_URL"):
        # Support full URL or just path
        url = os.environ["DATABASE_URL"]
        if url.startswith("sqlite"):
            return url
        path = Path(url)
    else:
        path = DEFAULT_DB_PATH

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    return f"sqlite:///{path}"


def create_db_engine(db_path: Path | str | None = None, echo: bool = False):
    """
    Create a SQLAlchemy engine for SQLite.

    Args:
        db_path: Optional path to the database file.
        echo: If True, log all SQL statements.

    Returns:
        SQLAlchemy Engine instance.
    """
    url = get_database_url(db_path)
    return create_engine(
        url,
        echo=echo,
        connect_args={"check_same_thread": False},  # Allow multi-threaded access
    )


# Global engine and session factory (initialized lazily)
_engine = None
_SessionLocal = None


def get_engine(db_path: Path | str | None = None, echo: bool = False):
    """Get or create the global database engine."""
    global _engine
    if _engine is None:
        _engine = create_db_engine(db_path, echo)
    return _engine


def get_session_factory(db_path: Path | str | None = None):
    """Get or create the global session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(db_path)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def reset_engine() -> None:
    """Reset the global engine and session factory (useful for testing)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


@contextmanager
def get_session(db_path: Path | str | None = None) -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with get_session() as session:
            # use session
            session.commit()

    Args:
        db_path: Optional path to the database file.

    Yields:
        SQLAlchemy Session instance.
    """
    session_factory = get_session_factory(db_path)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def init_db(db_path: Path | str | None = None) -> None:
    """
    Initialize the database by creating all tables.

    Note: In production, use Alembic migrations instead.

    Args:
        db_path: Optional path to the database file.
    """
    from wine_agent.db.models import Base

    engine = get_engine(db_path)
    Base.metadata.create_all(bind=engine)


def run_migrations(db_path: Path | str | None = None) -> None:
    """
    Run Alembic migrations to the latest revision.

    Args:
        db_path: Optional path to the database file.
    """
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")

    config = Config(str(alembic_ini))
    config.set_main_option("sqlalchemy.url", get_database_url(db_path))
    command.upgrade(config, "head")
