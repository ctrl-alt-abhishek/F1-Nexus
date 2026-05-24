"""
app/routers/races.py - /races/* endpoints.

Spec §5.13:
  GET /races/{year}               - All rounds for a season with circuit info
  GET /races/{year}/{round}       - Round detail, tire stints, top-3 degradation curves
  GET /races/{year}/{round}/laps  - Paginated lap data (filterable by driver/compound)

All SQLAlchemy calls are wrapped in asyncio.to_thread() per spec rule §12 #3.
"""

import asyncio
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import (
    DegradationPointSchema,
    LapSchema,
    PaginatedLapsSchema,
    RaceAnalysisSchema,
    RoundSchema,
    TireStintSchema,
)
from app.models.sql import Lap, RaceResult, Round
from app.ml.loader import models

router = APIRouter(prefix="/races", tags=["races"])


# ── GET /races/{year} ─────────────────────────────────────────────────────────

@router.get("/{year}", response_model=list[RoundSchema])
async def list_rounds(year: int, db: Session = Depends(get_db)):
    """All rounds for a season with circuit info, ordered by round number."""
    def _query():
        return (
            db.query(Round)
            .filter(Round.season_year == year)
            .order_by(Round.round_number)
            .all()
        )

    rounds = await asyncio.to_thread(_query)
    return rounds


# ── GET /races/{year}/{round} ─────────────────────────────────────────────────

@router.get("/{year}/{round_number}", response_model=RaceAnalysisSchema)
async def get_race_analysis(
    year: int,
    round_number: int,
    db: Session = Depends(get_db),
):
    """
    Full race analysis for a single round.

    Returns:
    - Round + circuit metadata
    - Tire stint timeline for every driver
    - Predicted vs actual degradation curves for the top 3 finishers
    """
    def _load_data():
        rnd = (
            db.query(Round)
            .filter(Round.season_year == year, Round.round_number == round_number)
            .first()
        )
        if rnd is None:
            return None, [], []

        laps = (
            db.query(Lap)
            .filter(Lap.round_id == rnd.id, Lap.is_valid == True)
            .order_by(Lap.driver_code, Lap.lap_number)
            .all()
        )
        results = (
            db.query(RaceResult)
            .filter(RaceResult.round_id == rnd.id)
            .order_by(RaceResult.finish_position)
            .all()
        )
        return rnd, laps, results

    rnd, laps, results = await asyncio.to_thread(_load_data)

    if rnd is None:
        raise HTTPException(404, f"Round {year}/{round_number} not found")

    total_laps = max((lap.lap_number for lap in laps if lap.lap_number), default=0)

    # Tire stints — synchronous, CPU-only
    tire_stints = _build_tire_stints(laps)

    # Degradation curves — for top 3 finishers only
    top3_codes = [
        r.driver_code for r in results[:3]
        if r.finish_position is not None
    ]
    winner_code = results[0].driver_code if results else None

    degradation_curves: dict[str, list[DegradationPointSchema]] = {}

    if models.degradation and top3_codes and laps:
        # Index laps by driver for efficiency
        laps_by_driver: dict[str, list[Lap]] = defaultdict(list)
        for lap in laps:
            laps_by_driver[lap.driver_code].append(lap)

        for driver_code in top3_codes:
            driver_laps = laps_by_driver.get(driver_code, [])
            if not driver_laps:
                continue
            # Run model inference in thread (XGBoost predict is blocking)
            curves = await asyncio.to_thread(
                _build_driver_curves, driver_laps, total_laps
            )
            if curves:
                degradation_curves[driver_code] = curves

    return RaceAnalysisSchema(
        round=rnd,
        winner_code=winner_code,
        total_laps=total_laps,
        tire_stints=tire_stints,
        degradation_curves=degradation_curves,
    )


# ── GET /races/{year}/{round}/laps ────────────────────────────────────────────

@router.get("/{year}/{round_number}/laps", response_model=PaginatedLapsSchema)
async def get_laps(
    year: int,
    round_number: int,
    driver_code: str | None = Query(None, description="Filter by 3-letter driver code"),
    compound: str | None = Query(None, description="Filter by compound (SOFT, MEDIUM, HARD…)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Paginated lap data for a race.

    Query params:
      driver_code  - e.g. 'VER' or 'NOR'
      compound     - e.g. 'SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET'
      page         - 1-indexed page number (default: 1)
      page_size    - rows per page, max 200 (default: 50)
    """
    def _query():
        rnd = (
            db.query(Round)
            .filter(Round.season_year == year, Round.round_number == round_number)
            .first()
        )
        if rnd is None:
            return None, 0

        q = db.query(Lap).filter(Lap.round_id == rnd.id)
        if driver_code:
            q = q.filter(Lap.driver_code == driver_code.upper())
        if compound:
            q = q.filter(Lap.compound == compound.upper())

        total = q.count()
        items = (
            q.order_by(Lap.driver_code, Lap.lap_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    result = await asyncio.to_thread(_query)
    items, total = result

    if items is None:
        raise HTTPException(404, f"Round {year}/{round_number} not found")

    return PaginatedLapsSchema(items=items, total=total, page=page, page_size=page_size)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_tire_stints(laps: list[Lap]) -> list[TireStintSchema]:
    """
    Group laps by (driver_code, stint) to build tire strategy bar data.
    Returns a list sorted by (driver, stint).
    """
    stints: dict[tuple, dict] = {}

    for lap in laps:
        if lap.stint is None or lap.lap_number is None:
            continue
        key = (lap.driver_code, lap.stint)
        if key not in stints:
            stints[key] = {
                "driver_code": lap.driver_code,
                "stint": lap.stint,
                "compound": lap.compound or "UNKNOWN",
                "start_lap": lap.lap_number,
                "end_lap": lap.lap_number,
            }
        else:
            stints[key]["end_lap"] = max(stints[key]["end_lap"], lap.lap_number)

    result = [
        TireStintSchema(
            driver_code=d["driver_code"],
            stint=d["stint"],
            compound=d["compound"],
            start_lap=d["start_lap"],
            end_lap=d["end_lap"],
            lap_count=d["end_lap"] - d["start_lap"] + 1,
        )
        for d in stints.values()
    ]
    result.sort(key=lambda x: (x.driver_code, x.stint))
    return result


def _build_driver_curves(
    driver_laps: list[Lap],
    total_laps: int,
) -> list[DegradationPointSchema]:
    """
    Build predicted vs actual degradation curve for a single driver.

    Picks the driver's longest stint, runs build_degradation_curve() on it,
    and pairs each predicted point with the actual lap time at that tire age.

    round_enc=0 is used (unknown circuit) — the model was trained on round_enc
    as a categorical identifier but 0 is a valid fallback for inference.
    """
    from app.ml.degradation.predict import build_degradation_curve

    # Group laps by stint
    stints: dict[int, list[Lap]] = defaultdict(list)
    for lap in driver_laps:
        if lap.stint is not None:
            stints[lap.stint].append(lap)

    if not stints:
        return []

    # Use the longest stint
    longest = max(stints, key=lambda s: len(stints[s]))
    stint_laps = sorted(stints[longest], key=lambda l: l.lap_number or 0)

    compound = stint_laps[0].compound or "MEDIUM"
    max_tire_age = len(stint_laps)
    lap_start = stint_laps[0].lap_number or 1

    # Actual lap times keyed by tyre_life
    actual_by_age: dict[int, float] = {
        lap.tyre_life: lap.lap_time_s
        for lap in stint_laps
        if lap.tyre_life is not None and lap.lap_time_s is not None
    }

    try:
        curve_df = build_degradation_curve(
            model=models.degradation,
            compound=compound,
            max_tire_age=max_tire_age,
            driver_enc=0,
            stint=longest,
            lap_start=lap_start,
            total_laps=total_laps,
            round_enc=0,  # Inference with unknown circuit — acceptable fallback
        )
    except Exception:
        return []

    return [
        DegradationPointSchema(
            tire_age=int(row["tire_age"]),
            predicted_lap_time_s=float(row["predicted_lap_time_s"]),
            actual_lap_time_s=actual_by_age.get(int(row["tire_age"])),
        )
        for _, row in curve_df.iterrows()
    ]
