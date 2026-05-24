"""
app/database.py - SQLAlchemy engine, session factory, and dependency injection.

Uses Neon.tech PostgreSQL in production (requires ?sslmode=require in DATABASE_URL).
Connection pooling is tuned for Render's free tier: low pool size, pre-ping to
handle connection drops from Neon's serverless scaling.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from contextlib import contextmanager

from app.config import settings


# psycopg2 connect_args for Neon.tech reliability:
#   connect_timeout=10    - fail fast if Neon endpoint is unreachable (don't hang forever)
#   keepalives_idle=30    - send TCP keepalive after 30s of idle (detects dropped connections)
#   keepalives_interval=5 - retry keepalive every 5s
#   keepalives_count=3    - give up after 3 failed keepalives (~45s total detection time)
_NEON_CONNECT_ARGS = {
    "connect_timeout": 10,
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 5,
    "keepalives_count": 3,
}

# pool_pre_ping=True: re-validates connection before use (essential for Neon serverless).
# pool_size=5: low number appropriate for a single Render free instance.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args=_NEON_CONNECT_ARGS,
)


def create_script_engine():
    """
    Create a NullPool engine for use in one-off scripts (seed_data.py, train_all.py).
    NullPool = no connection reuse, each execute() gets a fresh connection.
    This avoids stale pooled connections surviving across long FastF1 load pauses.
    """
    return create_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        connect_args=_NEON_CONNECT_ARGS,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def init_db() -> None:
    """
    Create all tables that don't already exist.
    This is called at startup as a safety net. Alembic handles schema migrations
    in production - this only matters for fresh local setups.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    Always closed after the request, even if an exception is raised.

    Usage:
        @router.get("/example")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager version for use outside of FastAPI dependency injection
    (e.g., in scripts and background workers).

    Usage:
        with get_db_context() as db:
            results = db.query(Model).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """Verify the database is reachable. Used in /health endpoint."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
