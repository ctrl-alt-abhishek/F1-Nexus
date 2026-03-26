"""
model/predict.py
Inference helpers and degradation curve generation.
"""

import pandas as pd
import numpy as np


def predict_stint(model, features_df: pd.DataFrame) -> pd.Series:
    """
    Predict lap times for a given feature DataFrame.

    Parameters
    ----------
    model : trained model
    features_df : pd.DataFrame
        Must have the same columns used during training.

    Returns
    -------
    pd.Series of predicted lap times (seconds).
    """
    predictions = model.predict(features_df)
    return pd.Series(predictions, index=features_df.index, name="PredictedLapTime")


def build_degradation_curve(
    model,
    compound: int,
    max_tire_age: int,
    driver_enc: int,
    stint_number: int,
    lap_start: int,
    total_laps: int,
) -> pd.DataFrame:
    """
    Generate a synthetic degradation curve for a given compound.

    Creates a feature matrix with tire ages from 1 to max_tire_age
    and predicts lap times to produce a smooth degradation curve.

    Parameters
    ----------
    model : trained model
    compound : int
        Encoded compound (0=SOFT, 1=MEDIUM, 2=HARD, 3=INTER, 4=WET).
    max_tire_age : int
        Maximum tire age to predict for.
    driver_enc : int
        Encoded driver identifier.
    stint_number : int
        Current stint number.
    lap_start : int
        Starting lap number for this stint.
    total_laps : int
        Total laps in the race.

    Returns
    -------
    pd.DataFrame with columns: tire_age, predicted_time
    """
    tire_ages = np.arange(1, max_tire_age + 1)
    lap_numbers = lap_start + tire_ages - 1

    synthetic = pd.DataFrame(
        {
            "tire_age": tire_ages.astype(float),
            "compound_enc": compound,
            "lap_number": lap_numbers.astype(float),
            "fuel_load_proxy": 1.0 - (lap_numbers.astype(float) / total_laps),
            "driver_enc": driver_enc,
            "stint_number": float(stint_number),
        }
    )

    predictions = model.predict(synthetic)

    return pd.DataFrame(
        {"tire_age": tire_ages, "predicted_time": predictions}
    )
