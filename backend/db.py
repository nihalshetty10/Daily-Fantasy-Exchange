import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# DATABASE_URL examples:
#   postgres:  postgresql+psycopg2://user:password@localhost:5432/proptrader
#   sqlite (fallback): sqlite:///proptrader.db
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///proptrader.db')

# Create engine with pre-ping to avoid stale connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db_session():
    """Yield a database session (to be used with context management)."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close() 