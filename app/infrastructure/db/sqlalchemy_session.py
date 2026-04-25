from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def _get_engine() -> Engine:
    return create_engine(get_settings().database_url, future=True)


@lru_cache
def _get_session_factory():
    return sessionmaker(bind=_get_engine(), autoflush=False, autocommit=False, future=True)


def get_session():
    session = _get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def __getattr__(name: str):
    if name == "engine":
        return _get_engine()
    if name == "SessionLocal":
        return _get_session_factory()
    if name == "DATABASE_URL":
        return get_settings().database_url
    raise AttributeError(name)
