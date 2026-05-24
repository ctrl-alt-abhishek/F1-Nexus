"""
app/services/fastf1_loader.py - FastF1 data fetching, cleaning, and DB seeding.

Key rules (from spec §12):
- FastF1 cache MUST be enabled before any session load (init_cache called at startup).
- LapTime is a timedelta - always convert with .dt.total_seconds().
- seed_round_to_db uses INSERT ... ON CONFLICT DO UPDATE for idempotency (safe to re-run).
"""

import logging
import time
from datetime import datetime

import fastf1
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.sql import (
    Circuit, Driver, DriverSeason, Constructor, Lap,
    Qualifying, RaceResult, Round, Season,
)

logger = logging.getLogger(__name__)


def patch_requests_timeout(timeout: float = 120.0):
    """
    Globally patch requests.Session.send to apply a default timeout
    if none is specified.
    """
    import requests
    original_send = requests.Session.send
    def new_send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = timeout
        return original_send(self, request, **kwargs)
    requests.Session.send = new_send


def init_cache() -> None:
    """
    Enable FastF1's local disk cache. MUST be called before any session load.
    Without this, every call re-downloads raw timing data (~50MB per race).
    Called once in main.py lifespan handler at startup.
    """
    patch_requests_timeout(120.0)
    fastf1.Cache.enable_cache(settings.FASTF1_CACHE_DIR)
    logger.info("FastF1 cache enabled at: %s", settings.FASTF1_CACHE_DIR)


def safe_session_load(session: fastf1.core.Session, **kwargs) -> None:
    """
    Load a session with cache corruption safety.
    If loading fails with the disk cache enabled, disable the cache
    temporarily to load directly from the API.
    """
    try:
        session.load(**kwargs)
    except Exception as e:
        logger.warning(
            "Failed to load session %s with cache: %s. Retrying with cache disabled.",
            session, e
        )
        with fastf1.Cache.disabled():
            session.load(**kwargs)


def load_session(
    year: int,
    round_number: int,
    session_type: str = "R",
) -> fastf1.core.Session:
    """
    Load and return a FastF1 session object.

    Args:
        year:         Season year (e.g. 2024)
        round_number: Round number within the season (1-indexed)
        session_type: 'R' (Race), 'Q' (Qualifying), 'FP1', 'FP2', 'FP3'

    Returns:
        A loaded FastF1 Session object.
    """
    session = fastf1.get_session(year, round_number, session_type)
    return session


def get_clean_laps(session: fastf1.core.Session) -> pd.DataFrame:
    """
    Load lap data from a session and apply all cleaning filters.

    Filtering removes:
    - Laps where LapTime is NaT (no recorded time)
    - Pit in/out laps (PitOutTime or PitInTime is not NaT)
    - Laps under safety car / VSC / red flag (TrackStatus != '1')
    - Statistical outliers: LapTime > session median + 2 * std

    Adds:
    - lap_time_s: LapTime converted to seconds (float)

    Returns:
        Cleaned DataFrame of valid racing laps.
    """
    # Use messages=False as expected by FastF1 3.8.3
    safe_session_load(session, laps=True, telemetry=False, weather=False, messages=False)
    laps = session.laps.copy() if session.laps is not None else None

    if laps is None or laps.empty or "LapTime" not in laps.columns:
        logger.warning("No laps returned or missing LapTime column for session %s", session)
        return pd.DataFrame()

    # 1. Drop laps with no recorded time
    laps = laps[laps["LapTime"].notna()].copy()

    # 2. Convert LapTime timedelta to seconds FIRST (spec rule: LapTime is a timedelta)
    laps.loc[:, "lap_time_s"] = laps["LapTime"].dt.total_seconds()

    # 3. Remove pit in/out laps (include them if both PitInTime and PitOutTime are NaT)
    laps = laps[laps["PitOutTime"].isna() & laps["PitInTime"].isna()].copy()

    # 4. Keep only green flag laps (TrackStatus == '1')
    laps = laps[laps["TrackStatus"] == "1"].copy()

    # 5. Remove statistical outliers (> median + 2*std)
    median = laps["lap_time_s"].median()
    std = laps["lap_time_s"].std()
    laps = laps[laps["lap_time_s"] <= median + 2 * std].copy()

    logger.info(
        "Clean laps: %d rows after filtering (session: %s %d R%d)",
        len(laps),
        session.event["EventName"],
        session.event.year,
        session.event.RoundNumber,
    )
    return laps.reset_index(drop=True)


def _upsert_circuit(session_obj: fastf1.core.Session, db: Session) -> Circuit:
    """Get or create Circuit record for this session's event."""
    event = session_obj.event
    circuit_name = event.get("CircuitName", event["EventName"])
    country = event.get("Country", None)
    city = event.get("Location", None)

    existing = db.query(Circuit).filter(Circuit.name == circuit_name).first()
    if existing:
        return existing

    circuit = Circuit(name=circuit_name, country=country, city=city)
    db.add(circuit)
    db.flush()
    return circuit


def _upsert_driver(driver_code: str, full_name: str | None, db: Session) -> Driver:
    """Get or create Driver record."""
    existing = db.query(Driver).filter(Driver.code == driver_code).first()
    if existing:
        return existing

    driver = Driver(code=driver_code, full_name=full_name)
    db.add(driver)
    db.flush()
    return driver


def _upsert_constructor(name: str, db: Session) -> Constructor:
    """Get or create Constructor record."""
    existing = db.query(Constructor).filter(Constructor.name == name).first()
    if existing:
        return existing

    constructor = Constructor(name=name)
    db.add(constructor)
    db.flush()
    return constructor


def seed_round_to_db(year: int, round_number: int, db: Session) -> str:
    """
    Load a full race weekend and upsert all data into PostgreSQL.

    Creates/updates:
    - Season, Circuit, Round
    - Drivers, Constructors, DriverSeason mappings
    - Laps (all clean racing laps)
    - Qualifying results
    - Race results

    Uses INSERT ... ON CONFLICT DO UPDATE via SQLAlchemy upsert for idempotency.
    Safe to re-run without creating duplicates.

    Returns:
        Name of the event (for logging).
    """
    # ── Load session ─────────────────────────────────────────────────────────
    race_session = load_session(year, round_number, "R")
    # Use messages=False as expected by FastF1 3.8.3
    safe_session_load(race_session, laps=True, telemetry=False, weather=False, messages=False)

    event = race_session.event
    event_name = event["EventName"]
    race_date = event["EventDate"].date() if hasattr(event["EventDate"], "date") else None

    # ── Season ───────────────────────────────────────────────────────────────
    if not db.query(Season).filter(Season.year == year).first():
        db.add(Season(year=year))
        db.flush()

    # ── Circuit ───────────────────────────────────────────────────────────────
    circuit = _upsert_circuit(race_session, db)

    # ── Round ─────────────────────────────────────────────────────────────────
    round_record = (
        db.query(Round)
        .filter(Round.season_year == year, Round.round_number == round_number)
        .first()
    )
    if not round_record:
        round_record = Round(
            season_year=year,
            round_number=round_number,
            circuit_id=circuit.id,
            race_date=race_date,
            name=event_name,
        )
        db.add(round_record)
        db.flush()

    round_id = round_record.id

    # ── Drivers + DriverSeason ────────────────────────────────────────────────
    results_df = race_session.results
    if results_df is not None and not results_df.empty:
        for _, row in results_df.iterrows():
            driver_code = str(row.get("Abbreviation", "???"))[:3]
            full_name = str(row.get("FullName", ""))
            team_name = str(row.get("TeamName", ""))

            _upsert_driver(driver_code, full_name, db)

            constructor = _upsert_constructor(team_name, db)

            if not (
                db.query(DriverSeason)
                .filter(
                    DriverSeason.driver_code == driver_code,
                    DriverSeason.season_year == year,
                )
                .first()
            ):
                db.add(DriverSeason(
                    driver_code=driver_code,
                    season_year=year,
                    constructor_id=constructor.id,
                    car_number=int(row.get("DriverNumber", 0)) or None,
                ))

        db.flush()

    # ── Clean laps ───────────────────────────────────────────────────────────
    # Delete existing laps for this round before re-inserting (cleaner than upsert on BigSerial PK)
    db.query(Lap).filter(Lap.round_id == round_id).delete()
    db.flush()

    clean_laps = get_clean_laps(race_session)
    if not clean_laps.empty:
        lap_objects = []
        for _, row in clean_laps.iterrows():
            driver_code = str(row.get("Driver", "???"))[:3]
            # Ensure the driver exists (sometimes laps have unknown drivers)
            _upsert_driver(driver_code, None, db)

            compound = str(row.get("Compound", "UNKNOWN")).upper()
            track_status = str(row.get("TrackStatus", "1"))

            lap_objects.append(Lap(
                round_id=round_id,
                driver_code=driver_code,
                lap_number=int(row.get("LapNumber", 0)),
                lap_time_s=float(row["lap_time_s"]),
                sector1_s=_safe_seconds(row.get("Sector1Time")),
                sector2_s=_safe_seconds(row.get("Sector2Time")),
                sector3_s=_safe_seconds(row.get("Sector3Time")),
                compound=compound if compound != "NAN" else None,
                tyre_life=_safe_int(row.get("TyreLife")),
                stint=_safe_int(row.get("Stint")),
                is_valid=True,
                track_status=track_status[:5],
                position=_safe_int(row.get("Position")),
            ))

        db.bulk_save_objects(lap_objects)
        db.flush()
        logger.info("Inserted %d laps for %s %d R%d", len(lap_objects), event_name, year, round_number)

    # ── Qualifying ───────────────────────────────────────────────────────────
    try:
        quali_session = load_session(year, round_number, "Q")
        # Use messages=False as expected by FastF1 3.8.3
        safe_session_load(quali_session, laps=True, telemetry=False, weather=False, messages=False)
        qual_results = quali_session.results

        if qual_results is not None and not qual_results.empty:
            db.query(Qualifying).filter(Qualifying.round_id == round_id).delete()
            db.flush()

            for _, row in qual_results.iterrows():
                driver_code = str(row.get("Abbreviation", "???"))[:3]
                _upsert_driver(driver_code, None, db)
                db.add(Qualifying(
                    round_id=round_id,
                    driver_code=driver_code,
                    q1_s=_safe_seconds(row.get("Q1")),
                    q2_s=_safe_seconds(row.get("Q2")),
                    q3_s=_safe_seconds(row.get("Q3")),
                    grid_position=_safe_int(row.get("GridPosition")),
                ))
            db.flush()
    except Exception as e:
        logger.warning("Could not load qualifying for %d R%d: %s", year, round_number, e)

    # ── Race results ─────────────────────────────────────────────────────────
    if results_df is not None and not results_df.empty:
        db.query(RaceResult).filter(RaceResult.round_id == round_id).delete()
        db.flush()

        for _, row in results_df.iterrows():
            driver_code = str(row.get("Abbreviation", "???"))[:3]
            position = _safe_int(row.get("Position"))
            points = float(row.get("Points", 0.0)) if row.get("Points") is not None else None
            status = str(row.get("Status", ""))[:50]
            fastest_lap = bool(row.get("FastestLap", False))

            db.add(RaceResult(
                round_id=round_id,
                driver_code=driver_code,
                finish_position=position,
                points=points,
                status=status,
                fastest_lap=fastest_lap,
            ))

        db.flush()

    db.commit()
    return event_name


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_seconds(value) -> float | None:
    """Convert a timedelta or NaT to seconds float, or return None."""
    try:
        if pd.isna(value):
            return None
        return float(value.total_seconds())
    except Exception:
        return None


def _safe_int(value) -> int | None:
    """Convert a value to int, or return None if NaN/None."""
    try:
        if pd.isna(value):
            return None
        return int(value)
    except Exception:
        return None
