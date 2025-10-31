"""SQLAlchemy engine and session configuration."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from server.core.config import DATABASE_DSN


if not DATABASE_DSN:
    raise RuntimeError("DATABASE_DSN must be set to initialise the database layer")


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_DSN, pool_pre_ping=True)

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

