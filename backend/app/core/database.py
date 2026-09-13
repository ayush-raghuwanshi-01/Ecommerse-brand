"""Database engine/session management (SQLAlchemy 2.x).

Production: PostgreSQL. Tests/dev fallback: SQLite. Row-level locking helpers
degrade gracefully on SQLite (conditional UPDATE guards provide safety there).
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all models."""


def _build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False, "timeout": settings.db_pool_timeout_seconds},
            pool_pre_ping=True,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA busy_timeout=30000")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        return engine
    return create_engine(
        url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        # Recycle connections before the server/firewall drops them idle
        # (Postgres' default idle timeout and most managed-DB proxies are <1h).
        pool_recycle=settings.db_pool_recycle_seconds,
    )


engine = _build_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, rolled back on error."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def supports_row_locking(db: Session) -> bool:
    """SELECT ... FOR UPDATE is only meaningful on PostgreSQL here."""
    return db.bind.dialect.name == "postgresql" if db.bind else False


def utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
