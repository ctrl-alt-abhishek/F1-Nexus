"""
scripts/seed_data.py - Seed PostgreSQL with historical F1 data via FastF1.

Run once locally. Seeds 2024 first, then 2023 and 2022 if Neon storage allows.

Storage check after each season:
  SELECT pg_size_pretty(pg_database_size('neondb'));
  Stop seeding if this approaches 400MB (leaving 100MB headroom on the 0.5GB Neon free tier).

Expected runtime: 45-90 minutes per year.
FastF1 cache in ../cache/ will be populated as a side effect.

Usage:
  poetry run python scripts/seed_data.py
  poetry run python scripts/seed_data.py --year 2024           # single year
  poetry run python scripts/seed_data.py --year 2024 --round 5 # single round
  poetry run python scripts/seed_data.py --start-round 3       # resume from round 3
"""

import argparse
import logging
import sys
import time
from contextlib import contextmanager
from pathlib import Path

backend_dir = Path(__file__).parent.parent.resolve()
parent_dir = backend_dir.parent.resolve()
sys.path = [str(backend_dir)] + [p for p in sys.path if Path(p).resolve() != parent_dir]

import fastf1
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import create_script_engine
from app.services.fastf1_loader import init_cache, seed_round_to_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SEASONS_TO_SEED = [2024, 2023, 2022]
NEON_STORAGE_LIMIT_MB = 400
SLEEP_BETWEEN_ROUNDS_S = 2
MAX_RETRIES = 3


# ── Fresh-connection context manager (NullPool - no stale connections) ────────

def make_session_factory():
    """Create a fresh NullPool engine + session factory per script run."""
    engine = create_script_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False), engine


@contextmanager
def fresh_db():
    """
    Context manager that gives a fresh DB session from a NullPool engine.
    Each call gets a brand-new TCP connection to Neon - no pooling, no stale state.
    On error: rolls back and re-raises (caller decides whether to retry or skip).
    """
    Session = _SESSION_FACTORY
    db = Session()
    try:
        yield db
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass  # rollback may also fail if connection is totally dead
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass


def get_db_size_mb() -> float:
    """Return current database size in MB using a fresh connection."""
    with fresh_db() as db:
        result = db.execute(text(
            "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"
        ))
        return float(result.scalar())


def get_round_count(year: int) -> int:
    """Get number of rounds in a season from FastF1 event schedule."""
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        return len(schedule)
    except Exception as e:
        logger.warning("Could not get schedule for %d: %s. Defaulting to 24.", year, e)
        return 24


def seed_round_with_retry(year: int, round_num: int, max_retries: int = MAX_RETRIES) -> str:
    """
    Seed a single round with up to max_retries attempts on connection failure.
    Each retry gets a completely fresh DB connection (NullPool).
    Raises on final failure.
    """
    for attempt in range(1, max_retries + 1):
        try:
            with fresh_db() as db:
                return seed_round_to_db(year, round_num, db)
        except Exception as e:
            err_str = str(e)
            is_conn_error = any(phrase in err_str for phrase in [
                "server closed the connection",
                "connection was closed",
                "OperationalError",
                "could not connect",
                "SSL connection",
                "timeout",
            ])

            if attempt < max_retries and is_conn_error:
                wait = attempt * 5  # 5s, 10s backoff
                logger.warning(
                    "  R%02d attempt %d/%d failed (connection error). Retrying in %ds...",
                    round_num, attempt, max_retries, wait,
                )
                time.sleep(wait)
            else:
                raise  # non-connection error, or final attempt


def seed_season(year: int, start_round: int = 1, end_round: int | None = None) -> bool:
    """
    Seed all rounds for a season. Returns False if storage limit hit.
    Each round gets a fresh DB connection - a dropped connection only fails that round.
    """
    total_rounds = get_round_count(year)
    end = end_round or total_rounds

    logger.info("=" * 60)
    logger.info("Seeding %d  (rounds %d-%d)", year, start_round, end)
    logger.info("=" * 60)

    for round_num in range(start_round, end + 1):
        # Check storage with its own fresh connection
        try:
            size_mb = get_db_size_mb()
        except Exception as e:
            logger.warning("Could not check DB size: %s. Continuing anyway.", e)
            size_mb = 0.0

        if size_mb >= NEON_STORAGE_LIMIT_MB:
            logger.warning(
                "Neon storage at %.1f MB (limit: %d MB). Stopping seed.",
                size_mb, NEON_STORAGE_LIMIT_MB,
            )
            return False

        # Seed the round (with retry on connection errors)
        try:
            event_name = seed_round_with_retry(year, round_num)
            logger.info(
                "[%d/%d] %s %d  R%02d — OK  (DB: %.1f MB)",
                round_num, end, event_name, year, round_num, size_mb,
            )
        except Exception as e:
            # Log and continue to next round - one bad round doesn't abort the season
            logger.error(
                "[%d/%d] %d R%02d — ERROR (skipping): %s",
                round_num, end, year, round_num, e,
            )

        if round_num < end:
            time.sleep(SLEEP_BETWEEN_ROUNDS_S)

    # Final summary with fresh connection
    try:
        with fresh_db() as db:
            final_size = float(db.execute(text(
                "SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"
            )).scalar())
            lap_count = db.execute(text("SELECT COUNT(*) FROM laps")).scalar()
        logger.info(
            "Season %d complete. Laps: %d  DB size: %.1f MB",
            year, lap_count, final_size,
        )
    except Exception as e:
        logger.warning("Could not fetch final stats: %s", e)

    return True


def main():
    parser = argparse.ArgumentParser(description="Seed F1 Nexus database from FastF1")
    parser.add_argument("--year", type=int, help="Seed a specific year only")
    parser.add_argument("--round", type=int, dest="round_num", help="Seed a specific round (requires --year)")
    parser.add_argument("--start-round", type=int, default=1, help="Start from this round number (default: 1)")
    args = parser.parse_args()

    # Enable FastF1 cache first
    init_cache()
    logger.info("FastF1 cache: %s", settings.FASTF1_CACHE_DIR)

    if args.year and args.round_num:
        logger.info("Seeding %d Round %d only", args.year, args.round_num)
        event_name = seed_round_with_retry(args.year, args.round_num)
        logger.info("Done: %s", event_name)

    elif args.year:
        seed_season(args.year, start_round=args.start_round)

    else:
        for year in SEASONS_TO_SEED:
            ok = seed_season(year, start_round=args.start_round if year == SEASONS_TO_SEED[0] else 1)
            if not ok:
                logger.warning("Storage limit reached. Stopping.")
                break

    logger.info("Seed complete.")
    logger.info("Next step: run  poetry run python scripts/train_all.py --skip-style")


# Initialize NullPool session factory on import
_script_engine = create_script_engine()
_SESSION_FACTORY = sessionmaker(bind=_script_engine, autocommit=False, autoflush=False)


if __name__ == "__main__":
    main()

