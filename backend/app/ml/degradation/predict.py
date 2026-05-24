"""
app/ml/degradation/predict.py - Inference helpers and degradation curve generation.

Ported and upgraded from model/predict.py. Key changes:
- predict_stint returns np.ndarray (not pd.Series) per spec
- build_degradation_curve column names match spec: 'tire_age', 'predicted_lap_time_s'
- Feature column order matches FEATURE_COLS in features.py
"""

import pandas as pd
import numpy as np

from app.ml.degradation.features import FEATURE_COLS


def predict_stint(model, features_df: pd.DataFrame) -> np.ndarray:
    """
    Run inference on a feature DataFrame and return predicted lap times in seconds.

    features_df must have the same columns as FEATURE_COLS in the correct order.
    Returns a numpy array of floats, one predicted time per row.
    """
    return model.predict(features_df[FEATURE_COLS])


def build_degradation_curve(
    model,
    compound: str,
    max_tire_age: int,
    driver_enc: int,
    stint: int,
    lap_start: int,
    total_laps: int,
    round_enc: int = 0,
) -> pd.DataFrame:
    """
    Generate a smooth predicted degradation curve for a given compound and driver.

    Creates a synthetic feature matrix for tire ages 1..max_tire_age, then runs
    the model to produce predicted lap times. Used by the race analysis page to
    overlay predicted vs actual lap times.

    Args:
        compound:     Compound name string ('SOFT', 'MEDIUM', 'HARD', 'INTER', 'WET')
        max_tire_age: Maximum tire age to predict up to (e.g. 30 for a long stint)
        driver_enc:   Integer-encoded driver ID from get_driver_map()
        stint:        Stint number (affects fuel_proxy calculation context)
        lap_start:    Lap number when this stint began
        total_laps:   Total laps in the race (for fuel_proxy)

    Returns:
        DataFrame with columns: ['tire_age', 'predicted_lap_time_s']
    """
    from app.ml.degradation.features import COMPOUND_MAP

    compound_enc = COMPOUND_MAP.get(compound.upper(), 1)  # default to MEDIUM if unknown
    tire_ages = np.arange(1, max_tire_age + 1)
    lap_numbers = lap_start + tire_ages - 1

    synthetic = pd.DataFrame({
        "tire_age": tire_ages.astype(float),
        "compound_enc": float(compound_enc),
        "lap_number": lap_numbers.astype(float),
        "fuel_proxy": 1.0 - (lap_numbers.astype(float) / max(total_laps, 1)),
        "driver_enc": float(driver_enc),
        "stint": float(stint),
        "track_temp_proxy": lap_numbers.astype(float) / 10.0,
        "round_enc": float(round_enc),
    })

    predictions = model.predict(synthetic[FEATURE_COLS])

    return pd.DataFrame({
        "tire_age": tire_ages,
        "predicted_lap_time_s": predictions,
    })
