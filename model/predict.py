"""
model/predict.py - Inference helpers and degradation curve generation.
"""

import pandas as pd
import numpy as np


def predict_stint(model, features_df: pd.DataFrame) -> pd.Series:
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
