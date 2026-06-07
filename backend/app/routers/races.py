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

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session, joinedload

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
async def list_rounds(
    year: int = Path(..., ge=2018, le=2030, description="Season year"),
    db: Session = Depends(get_db),
):
    """All rounds for a season with circuit info, ordered by round number."""
    def _query():
        return (
            db.query(Round)
            .filter(Round.season_year == year)
            .options(
                joinedload(Round.circuit),
                joinedload(Round.race_results)
            )
            .order_by(Round.round_number)
            .all()
        )

    rounds = await asyncio.to_thread(_query)
    return rounds


# ── GET /races/{year}/{round} ─────────────────────────────────────────────────

@router.get("/{year}/{round_number}", response_model=RaceAnalysisSchema)
async def get_race_analysis(
    year: int = Path(..., ge=2018, le=2030, description="Season year"),
    round_number: int = Path(..., ge=1, le=24, description="Round number"),
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
    tire_stints = build_tire_stints(laps)

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
                build_driver_curves, driver_laps, total_laps
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
    year: int = Path(..., ge=2018, le=2030, description="Season year"),
    round_number: int = Path(..., ge=1, le=24, description="Round number"),
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


from app.services.race_service import build_tire_stints, build_driver_curves
