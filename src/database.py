import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Default SQLite (safe fallback)
DEFAULT_SQLITE_URL = "sqlite:///./app.db"
TEST_SQLITE_URL = "sqlite:///./test.db"


def is_pytest_running() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


# Decide DB URL
if is_pytest_running():
    DATABASE_URL = TEST_SQLITE_URL
else:
    DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL)


# SQLite needs special args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}


engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

