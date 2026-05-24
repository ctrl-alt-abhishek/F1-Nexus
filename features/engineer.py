"""
features/engineer.py - Feature engineering pipeline for lap time degradation prediction.
"""

import pandas as pd
import numpy as np


COMPOUND_MAP = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "WET": 4,
}


def build_features(laps_df: pd.DataFrame):
    df = laps_df.copy()

    df["tire_age"] = df["TyreLife"].astype(float)
    df["compound_enc"] = df["Compound"].map(COMPOUND_MAP).fillna(1).astype(int)
    df["lap_number"] = df["LapNumber"].astype(float)

    total_laps = df["LapNumber"].max()
    df["fuel_load_proxy"] = 1.0 - (df["LapNumber"].astype(float) / total_laps)

    driver_codes = sorted(df["Driver"].unique())
    driver_map = {code: idx for idx, code in enumerate(driver_codes)}
    df["driver_enc"] = df["Driver"].map(driver_map).astype(int)

    df["stint_number"] = df["Stint"].astype(float)

    feature_cols = [
        "tire_age",
        "compound_enc",
        "lap_number",
        "fuel_load_proxy",
        "driver_enc",
        "stint_number",
    ]
    X = df[feature_cols].copy()
    y = df["LapTimeSeconds"].copy()

    return X, y
