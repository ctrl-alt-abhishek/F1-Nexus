"""
app/routers/drivers.py - /drivers/* endpoints.

Spec §5.13:
  GET /drivers                             - All drivers with current team
  GET /drivers/{code}                      - Driver profile + career stats
  GET /drivers/{code}/style                - Style cluster + PCA coords (404 if not trained)
  GET /drivers/{code}/compare/{other_code} - Sector delta vs another driver (query: round_id)

All blocking DB calls wrapped in asyncio.to_thread() per spec §12 #3.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.loader import models
from app.models.schemas import (
    CareerStatsSchema,
    DriverProfileSchema,
    DriverWithTeamSchema,
    SectorDeltaSchema,
    StyleFeaturesSchema,
)
from app.models.sql import (
    Constructor,
    Driver,
    DriverSeason,
    Lap,
    Qualifying,
    RaceResult,
    Round,
)

router = APIRouter(prefix="/drivers", tags=["drivers"])


# ── GET /drivers ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[DriverWithTeamSchema])
async def list_drivers(
    year: int = Query(2024, ge=2018, le=2030, description="Season year for team lookup"),
    db: Session = Depends(get_db),
):
    """All drivers with their constructor for the given season."""
    def _query():
        rows = (
            db.query(Driver, DriverSeason, Constructor)
            .outerjoin(DriverSeason, and_(
                DriverSeason.driver_code == Driver.code,
                DriverSeason.season_year == year,
            ))
            .outerjoin(Constructor, Constructor.id == DriverSeason.constructor_id)
            .filter(DriverSeason.season_year == year)
            .order_by(Driver.full_name)
            .all()
        )
        result = []
        for driver, ds, constructor in rows:
            result.append(DriverWithTeamSchema(
                code=driver.code,
                full_name=driver.full_name,
                nationality=driver.nationality,
                dob=driver.dob,
                team=constructor.name if constructor else None,
                car_number=ds.car_number if ds else None,
            ))
        return result

    return await asyncio.to_thread(_query)


# ── GET /drivers/{code} ───────────────────────────────────────────────────────

@router.get("/{code}", response_model=DriverProfileSchema)
async def get_driver(code: str, db: Session = Depends(get_db)):
    """Driver profile with career statistics across all seeded seasons."""
    code = code.upper()

    def _query():
        from app.services.driver_service import get_career_stats
        return get_career_stats(code, db)

    driver_schema, stats = await asyncio.to_thread(_query)

    if driver_schema is None:
        raise HTTPException(404, f"Driver '{code}' not found")

    return DriverProfileSchema(driver=driver_schema, career_stats=stats)


# ── GET /drivers/{code}/style ─────────────────────────────────────────────────

@router.get("/{code}/style", response_model=StyleFeaturesSchema)
async def get_driver_style(code: str):
    """
    Driver style cluster assignment and PCA coordinates.

    Returns 404 if the style model has not been trained yet.
    To train: poetry run python scripts/train_all.py --model style
    """
    code = code.upper()

    if not models.style_available:
        raise HTTPException(
            503,
            detail=(
                "Driver style model not trained yet. "
                "Run: poetry run python scripts/train_all.py --model style"
            ),
        )

    cluster_map = models.style_cluster_map or {}
    pca_coords = models.style_pca_coords or {}

    if code not in cluster_map:
        raise HTTPException(
            404,
            detail=f"Driver '{code}' not in style model. "
                   f"Available: {sorted(cluster_map.keys())}",
        )

    from app.ml.driver_style.cluster import CLUSTER_LABELS

    cluster_id = cluster_map[code]
    coords = pca_coords.get(code, [0.0, 0.0])

    return StyleFeaturesSchema(
        driver_code=code,
        cluster_id=cluster_id,
        cluster_description=CLUSTER_LABELS.get(cluster_id, "Unknown"),
        pca_x=coords[0],
        pca_y=coords[1],
        features={},  # Raw feature values available after full style training
    )


# ── GET /drivers/{code}/compare/{other_code} ──────────────────────────────────

@router.get("/{code}/compare/{other_code}", response_model=list[SectorDeltaSchema])
async def compare_drivers(
    code: str,
    other_code: str,
    round_id: int = Query(..., description="Round ID from /races/{year}"),
    db: Session = Depends(get_db),
):
    """
    Sector-level comparison between two drivers for a specific race round.

    Returns sector time deltas (positive = driver is slower than other_code).
    Computes deltas using the median sector time across all clean laps in the round
    for each driver, to reduce noise from individual lap anomalies.
    """
    code = code.upper()
    other_code = other_code.upper()

    def _query():
        from app.services.driver_service import compute_sector_deltas
        return compute_sector_deltas(code, other_code, round_id, db)

    a_meds, b_meds = await asyncio.to_thread(_query)

    if not a_meds:
        raise HTTPException(404, f"No laps found for {code} in round {round_id}")
    if not b_meds:
        raise HTTPException(404, f"No laps found for {other_code} in round {round_id}")

    def _delta(key: str) -> float | None:
        va, vb = a_meds.get(key), b_meds.get(key)
        if va is None or vb is None:
            return None
        return round(va - vb, 4)

    return [
        SectorDeltaSchema(
            driver_code=code,
            sector1_delta_s=_delta("s1"),
            sector2_delta_s=_delta("s2"),
            sector3_delta_s=_delta("s3"),
            lap_time_delta_s=_delta("lt"),
        ),
        SectorDeltaSchema(
            driver_code=other_code,
            sector1_delta_s=-_delta("s1") if _delta("s1") is not None else None,
            sector2_delta_s=-_delta("s2") if _delta("s2") is not None else None,
            sector3_delta_s=-_delta("s3") if _delta("s3") is not None else None,
            lap_time_delta_s=-_delta("lt") if _delta("lt") is not None else None,
        ),
    ]
