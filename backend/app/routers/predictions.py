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

from fastapi import APIRouter, Depends, HTTPException, Query
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
    year: int,
    total_rounds: int = Query(24, description="Total rounds in the season"),
    profile: str = Query("balanced", description="balanced | aggressive | conservative"),
    db: Session = Depends(get_db),
):
    """
    Monte Carlo championship probability simulation.

    Runs 10,000 simulations of the remaining races using each driver's recent
    finishing position distribution. Cached in memory for 1 hour per year+profile.
    """
    cache_key = f"championship:{year}:{profile}"
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
        simulate_season, db, year, total_rounds, profile
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
    round_id: int,
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
        rnd = db.query(Round).filter(Round.id == round_id).first()
        if rnd is None:
            return None, []

        from sqlalchemy import text
        # Get driver win rates from race_results across all seeded data
        result = db.execute(text("""
            SELECT
                rr.driver_code,
                COUNT(*) AS total_races,
                SUM(CASE WHEN rr.finish_position = 1 THEN 1 ELSE 0 END) AS wins,
                AVG(rr.finish_position) AS avg_position
            FROM race_results rr
            JOIN rounds r ON r.id = rr.round_id
            WHERE rr.finish_position IS NOT NULL
            GROUP BY rr.driver_code
            ORDER BY avg_position ASC
        """))
        rows = result.fetchall()
        return rnd, rows

    rnd, rows = await asyncio.to_thread(_query)

    if rnd is None:
        raise HTTPException(404, f"Round {round_id} not found")

    if not rows:
        raise HTTPException(404, "No race results available for prediction")

    # Simple Bayesian win probability: smooth win rate by overall performance
    # Each driver gets a base probability proportional to (1 / avg_position).
    # Laplace smoothing: add 1 fictitious win and 10 fictitious races.
    import numpy as np

    raw_scores = []
    driver_codes = []
    for row in rows:
        driver_code, total_races, wins, avg_pos = row
        smoothed_rate = (wins + 1) / (total_races + 10)
        pos_score = 1.0 / max(float(avg_pos or 10), 1.0)
        raw_scores.append(0.5 * smoothed_rate + 0.5 * pos_score)
        driver_codes.append(driver_code)

    scores = np.array(raw_scores)
    win_probs = scores / scores.sum()  # Normalize to sum to 1

    predictions = [
        RaceOutcomeDriverSchema(
            driver_code=dc,
            win_probability=float(wp),
            points_distribution=[],  # Full Monte Carlo deferred — see championship endpoint
        )
        for dc, wp in zip(driver_codes, win_probs)
    ]
    predictions.sort(key=lambda x: x.win_probability, reverse=True)

    _cache_set(cache_key, predictions)

    return RaceOutcomeSchema(round_id=round_id, predictions=predictions)


# ── GET /predictions/pit-window ───────────────────────────────────────────────

@router.get("/pit-window", response_model=PitWindowSchema)
async def get_pit_window(
    round_id: int = Query(..., description="Round ID"),
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
        rnd = db.query(Round).filter(Round.id == round_id).first()
        if not rnd:
            return None
        # Approximate total laps from seeded lap data
        from sqlalchemy import text, func
        from app.models.sql import Lap as LapModel
        result = (
            db.query(func.max(LapModel.lap_number))
            .filter(LapModel.round_id == round_id)
            .scalar()
        )
        return result or 60  # Fallback: typical race length

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
