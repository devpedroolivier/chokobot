from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import get_settings


DATABASE_URL = get_settings().database_url


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
