"""
app/routers/predictions.py - /predictions/* endpoints.

Spec §5.13:
  GET /predictions/championship/{year}  - Monte Carlo championship simulation (cached 1hr)
  GET /predictions/race/{round_id}      - Per-driver win probabilities for upcoming race
  GET /predictions/pit-window           - Pit stop recommendation for current lap

In-memory _prediction_cache dict used instead of Redis (single Render instance).
Cache key format: "{endpoint}:{params}" → (unix_timestamp, data)
"""

import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.loader import models
from app.models.schemas import (
    ChampionshipPredictionSchema,
    DriverChampionshipPredSchema,
    PitProbabilitySchema,
    PitWindowSchema,
    RaceOutcomeDriverSchema,
    RaceOutcomeSchema,
)
from app.models.sql import Round

router = APIRouter(prefix="/predictions", tags=["predictions"])

# ── In-memory prediction cache ────────────────────────────────────────────────
# Format: key → (created_at_unix_float, data)
# Single dict is thread-safe for reads in CPython (GIL). Writes are rare (1/hr).
_prediction_cache: dict[str, tuple[float, object]] = {}
CACHE_TTL = 3600  # 1 hour in seconds


def _cache_get(key: str):
    """Return cached value if still fresh, else None."""
    entry = _prediction_cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > CACHE_TTL:
        del _prediction_cache[key]
        return None
    return data


def _cache_set(key: str, data) -> None:
    _prediction_cache[key] = (time.time(), data)


# ── GET /predictions/championship/{year} ──────────────────────────────────────

@router.get("/championship/{year}", response_model=ChampionshipPredictionSchema)
async def get_championship_prediction(
    year: int = Path(..., ge=2018, le=2030, description="Season year"),
    total_rounds: int | None = Query(None, description="Total rounds in the season"),
    profile: str = Query("balanced", description="balanced | aggressive | conservative"),
    db: Session = Depends(get_db),
):
    """
    Monte Carlo championship probability simulation.

    Runs 10,000 simulations of the remaining races using each driver's recent
    finishing position distribution. Cached in memory for 1 hour per year+profile.
    """
    if total_rounds is None:
        # Determine total rounds dynamically from database rounds table for this year
        # Falls back to 24 if no rounds are registered
        from app.models.sql import Round as SqlRound
        total_rounds = db.query(SqlRound).filter(SqlRound.season_year == year).count() or 24

    cache_key = f"championship:{year}:{profile}:{total_rounds}"
    cached = _cache_get(cache_key)

    if cached is not None:
        return ChampionshipPredictionSchema(
            year=year,
            drivers=[DriverChampionshipPredSchema(**d) for d in cached],
            simulations_run=10_000,
            cached=True,
        )

    from app.ml.season_prediction.monte_carlo import simulate_season

    results = await asyncio.to_thread(
        simulate_season, db, year, total_rounds, profile, 42
    )

    if not results:
        raise HTTPException(
            404,
            detail=f"No race results found for {year}. Seed the database first.",
        )

    _cache_set(cache_key, results)

    return ChampionshipPredictionSchema(
        year=year,
        drivers=[DriverChampionshipPredSchema(**d) for d in results],
        simulations_run=10_000,
        cached=False,
    )


# ── GET /predictions/race/{round_id} ─────────────────────────────────────────

@router.get("/race/{round_id}", response_model=RaceOutcomeSchema)
async def get_race_prediction(
    round_id: int = Path(..., ge=1, description="Round ID"),
    db: Session = Depends(get_db),
):
    """
    Win probability predictions for an upcoming race.

    Uses historical performance at this circuit (or overall form if no circuit
    history exists). Results are cached for 1 hour.
    """
    cache_key = f"race:{round_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return RaceOutcomeSchema(round_id=round_id, predictions=cached)

    def _query():
        from app.services.prediction_service import compute_race_win_probabilities
        return compute_race_win_probabilities(round_id, db)

    predictions = await asyncio.to_thread(_query)

    if predictions is None:
        raise HTTPException(404, f"Round {round_id} not found")

    if not predictions:
        raise HTTPException(404, "No race results available for prediction")

    _cache_set(cache_key, predictions)

    return RaceOutcomeSchema(round_id=round_id, predictions=predictions)


# ── GET /predictions/pit-window ───────────────────────────────────────────────

@router.get("/pit-window", response_model=PitWindowSchema)
async def get_pit_window(
    round_id: int = Query(..., ge=1, description="Round ID"),
    driver_code: str = Query(..., description="3-letter driver code, e.g. VER"),
    current_lap: int = Query(..., ge=1),
    tire_age: int = Query(..., ge=1, description="Current tyre life in laps"),
    compound: str = Query("MEDIUM", description="Current tyre compound"),
    position: int = Query(10, ge=1, le=20, description="Current race position"),
    gap_ahead: float = Query(0.0, description="Gap to car ahead in seconds"),
    db: Session = Depends(get_db),
):
    """
    Pit stop window recommendation for the next 5 laps.

    Uses the strategy classifier (XGBClassifier) trained on historical pit patterns.
    Returns probabilities for laps [current_lap, current_lap+4] and a recommended lap.
    """
    if models.strategy is None:
        raise HTTPException(
            503, "Strategy model not loaded. Run train_all.py first."
        )

    def _get_total_laps():
        from app.services.prediction_service import get_total_laps_for_round
        return get_total_laps_for_round(round_id, db)

    total_laps = await asyncio.to_thread(_get_total_laps)
    if total_laps is None:
        raise HTTPException(404, f"Round {round_id} not found")

    from app.ml.strategy.predict import recommend_pit_window

    result = await asyncio.to_thread(
        recommend_pit_window,
        models.strategy,
        models.degradation,
        current_lap,
        tire_age,
        compound,
        position,
        gap_ahead,
        total_laps,
        driver_enc=0,
        stint=1,
    )

    return PitWindowSchema(
        recommended_lap=result["recommended_lap"],
        probabilities=[
            PitProbabilitySchema(lap=p["lap"], pit_probability=p["pit_probability"])
            for p in result["probabilities"]
        ],
        reasoning=result["reasoning"],
    )
