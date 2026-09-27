"""Database engine / session layer.

The spec asks for PostgreSQL. To keep the product runnable on a machine without
a PG server we use SQLAlchemy ORM with a ``DATABASE_URL`` switch:

* default  -> ``sqlite:///./data/gengv1.db``  (relative paths resolve to backend/)
* production -> ``postgresql+psycopg2://...``

Nothing in the models or queries below is SQLite-specific.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import BACKEND_DIR, settings


def _normalise_url(raw: str) -> str:
    """Make relative SQLite paths independent of the current working dir."""
    url = make_url(raw)
    if url.get_backend_name() != "sqlite":
        return raw
    database = url.database or ""
    if database in {"", ":memory:"}:
        return raw
    path = Path(database.replace("///", "/").lstrip("/") if database.startswith("///") else database)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.as_posix()}"


DATABASE_URL = _normalise_url(settings.database_url)
IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_MEMORY = ":memory:" in DATABASE_URL

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if IS_MEMORY:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver hook
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables for models that have been imported."""
    from app import models  # noqa: F401  (ensures registration)

    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
