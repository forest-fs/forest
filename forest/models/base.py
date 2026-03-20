"""
Declarative base for all ORM models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 declarative base shared by all mapped classes.

    Notes
    -----
    :attr:`metadata` is consumed by Alembic for autogenerate and revision baselines.
    """

    pass
