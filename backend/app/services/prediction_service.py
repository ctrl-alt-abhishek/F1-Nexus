"""
app/services/prediction_service.py - Business logic for predictions.
"""

import numpy as np
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Dict, Any

from app.models.sql import Round, Lap as LapModel
from app.models.schemas import RaceOutcomeDriverSchema

def compute_race_win_probabilities(round_id: int, db: Session) -> Optional[List[RaceOutcomeDriverSchema]]:
    rnd = db.query(Round).filter(Round.id == round_id).first()
    if rnd is None:
        return None

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
    
    if not rows:
        return []

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
    return predictions

def get_total_laps_for_round(round_id: int, db: Session) -> Optional[int]:
    rnd = db.query(Round).filter(Round.id == round_id).first()
    if not rnd:
        return None
    # Approximate total laps from seeded lap data
    result = (
        db.query(func.max(LapModel.lap_number))
        .filter(LapModel.round_id == round_id)
        .scalar()
    )
    return result or 60  # Fallback: typical race length
