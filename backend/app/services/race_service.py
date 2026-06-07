"""
app/services/race_service.py - Business logic for race data and analysis.
"""

from collections import defaultdict
from app.models.sql import Lap
from app.models.schemas import TireStintSchema, DegradationPointSchema
from app.ml.loader import models

def build_tire_stints(laps: list[Lap]) -> list[TireStintSchema]:
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

def build_driver_curves(
    driver_laps: list[Lap],
    total_laps: int,
) -> list[DegradationPointSchema]:
    """
    Build predicted vs actual degradation curve for a single driver.
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
            round_enc=0,  # Inference with unknown circuit
        )
    except Exception:
        return []

    if curve_df is None or curve_df.empty or "tire_age" not in curve_df.columns or "predicted_lap_time_s" not in curve_df.columns:
        return []

    return [
        DegradationPointSchema(
            tire_age=int(row["tire_age"]),
            predicted_lap_time_s=float(row["predicted_lap_time_s"]),
            actual_lap_time_s=actual_by_age.get(int(row["tire_age"])),
        )
        for _, row in curve_df.iterrows()
    ]
