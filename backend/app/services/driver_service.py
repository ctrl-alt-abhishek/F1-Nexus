"""
app/services/driver_service.py - Business logic for driver data and statistics.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Tuple, Dict, Any, Optional

from app.models.sql import Driver, DriverSeason, Constructor, RaceResult, Qualifying, Lap
from app.models.schemas import DriverWithTeamSchema, CareerStatsSchema

def get_career_stats(code: str, db: Session) -> Tuple[Optional[DriverWithTeamSchema], Optional[CareerStatsSchema]]:
    """Fetch driver profile and career statistics."""
    driver = db.query(Driver).filter(Driver.code == code).first()
    if not driver:
        return None, None

    # Latest team
    latest_ds = (
        db.query(DriverSeason, Constructor)
        .outerjoin(Constructor, Constructor.id == DriverSeason.constructor_id)
        .filter(DriverSeason.driver_code == code)
        .order_by(DriverSeason.season_year.desc())
        .first()
    )
    team_name = latest_ds[1].name if latest_ds and latest_ds[1] else None
    car_number = latest_ds[0].car_number if latest_ds else None

    # Career results
    results = (
        db.query(RaceResult)
        .filter(RaceResult.driver_code == code)
        .all()
    )
    races = len(results)
    wins = sum(1 for r in results if r.finish_position == 1)
    podiums = sum(1 for r in results if r.finish_position is not None and r.finish_position <= 3)
    points_total = sum(r.points or 0.0 for r in results)

    # Poles from qualifying
    poles = (
        db.query(func.count(Qualifying.id))
        .filter(Qualifying.driver_code == code, Qualifying.grid_position == 1)
        .scalar()
    ) or 0

    # Seasons active
    seasons = [
        row[0] for row in
        db.query(DriverSeason.season_year)
        .filter(DriverSeason.driver_code == code)
        .order_by(DriverSeason.season_year)
        .all()
    ]

    driver_schema = DriverWithTeamSchema(
        code=driver.code,
        full_name=driver.full_name,
        nationality=driver.nationality,
        dob=driver.dob,
        team=team_name,
        car_number=car_number,
    )
    stats = CareerStatsSchema(
        races=races,
        wins=wins,
        podiums=podiums,
        poles=poles,
        points_total=points_total,
        seasons=seasons,
    )
    return driver_schema, stats

def _median(lst: list[float]) -> Optional[float]:
    """Helper to calculate median of a list of floats."""
    if not lst:
        return None
    s = sorted(lst)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    else:
        return (s[n // 2 - 1] + s[n // 2]) / 2.0

def compute_sector_deltas(code: str, other_code: str, round_id: int, db: Session) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    """
    Compute median sector times and lap times for two drivers in a specific round.
    Returns (code_medians, other_code_medians).
    """
    def _driver_medians(driver: str) -> dict:
        rows = (
            db.query(Lap)
            .filter(
                Lap.round_id == round_id,
                Lap.driver_code == driver,
                Lap.is_valid == True,
            )
            .all()
        )
        if not rows:
            return {}
        s1 = [r.sector1_s for r in rows if r.sector1_s is not None]
        s2 = [r.sector2_s for r in rows if r.sector2_s is not None]
        s3 = [r.sector3_s for r in rows if r.sector3_s is not None]
        lt = [r.lap_time_s for r in rows if r.lap_time_s is not None]
        return {
            "s1": _median(s1),
            "s2": _median(s2),
            "s3": _median(s3),
            "lt": _median(lt),
        }

    a = _driver_medians(code)
    b = _driver_medians(other_code)
    return a, b
