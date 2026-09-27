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
    """建表 + 补齐新增列。"""
    from app import models  # noqa: F401  (ensures registration)

    Base.metadata.create_all(bind=engine)


def ensure_schema() -> list[str]:
    """给已有库补上新增列（轻量迁移，避免"改模型就得删库"）。

    只处理"新增带默认值的列"这一种情况——本项目到目前为止的演进都是这种。
    需要改类型/删列时请重新跑 seed。
    """
    from sqlalchemy import inspect, text

    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    added: list[str] = []

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            column_type = column.type.compile(engine.dialect)
            default = "NULL"
            if column.default is not None and column.default.is_scalar:
                value = column.default.arg
                default = f"'{value}'" if isinstance(value, str) else str(value)
            elif not column.nullable:
                default = "0" if "INT" in column_type.upper() else "''"
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type} DEFAULT {default}"))
            added.append(f"{table.name}.{column.name}")

    if added:
        from app.config import get_logger

        get_logger(__name__).info("已补齐数据库列：%s", ", ".join(added))
    return added


def reset_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
