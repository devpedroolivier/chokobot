"""
SQLAlchemy models will progressively replace raw sqlite usage.
Start with read-only parity migrations before switching writes.
"""

from app.infrastructure.db.sqlalchemy_session import Base

__all__ = ["Base"]
