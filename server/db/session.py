"""SQLAlchemy engine and session configuration."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from server.core.config import DATABASE_DSN


if not DATABASE_DSN:
    raise RuntimeError("DATABASE_DSN must be set to initialise the database layer")


class Base(DeclarativeBase):
    pass


# Use a conservative connection pool to avoid exhausting Supabase Session pooler.
# The defaults here are tuned for a small-scale deployment. A pool size of 1
# is too restrictive for a webapp with background workers, leading to timeouts.
# We'll increase this to 5 with a small overflow allowance.
# Defaults can be overridden via env vars.
_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "10"))  # seconds to wait for a connection
_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "300"))  # seconds before recycling a connection

engine = create_engine(
    DATABASE_DSN,
    pool_pre_ping=True,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_timeout=_POOL_TIMEOUT,
    pool_recycle=_POOL_RECYCLE,
)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

