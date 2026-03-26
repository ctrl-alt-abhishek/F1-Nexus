"""
features/engineer.py
Feature engineering pipeline for lap time degradation prediction.
"""

import pandas as pd
import numpy as np


# Compound encoding map
COMPOUND_MAP = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "WET": 4,
}


def build_features(laps_df: pd.DataFrame):
    """
    Build feature matrix X and target vector y from cleaned laps DataFrame.

    Features engineered:
    - tire_age:         TyreLife (laps on current tyre set)
    - compound_enc:     Label-encoded compound (SOFT=0 … WET=4)
    - lap_number:       LapNumber in the race
    - fuel_load_proxy:  1 - (LapNumber / total_laps), fuel decreases linearly
    - driver_enc:       Label-encoded driver abbreviation
    - stint_number:     Stint number in the race

    Target:
    - LapTimeSeconds (float)

    Parameters
    ----------
    laps_df : pd.DataFrame
        Cleaned laps DataFrame from `data.loader.get_race_laps`.

    Returns
    -------
    X : pd.DataFrame
        Feature matrix.
    y : pd.Series
        Target vector (lap time in seconds).
    """
    df = laps_df.copy()

    # --- Tire age ---
    df["tire_age"] = df["TyreLife"].astype(float)

    # --- Compound encoding ---
    df["compound_enc"] = df["Compound"].map(COMPOUND_MAP).fillna(1).astype(int)

    # --- Lap number ---
    df["lap_number"] = df["LapNumber"].astype(float)

    # --- Fuel load proxy ---
    total_laps = df["LapNumber"].max()
    df["fuel_load_proxy"] = 1.0 - (df["LapNumber"].astype(float) / total_laps)

    # --- Driver encoding ---
    driver_codes = sorted(df["Driver"].unique())
    driver_map = {code: idx for idx, code in enumerate(driver_codes)}
    df["driver_enc"] = df["Driver"].map(driver_map).astype(int)

    # --- Stint number ---
    df["stint_number"] = df["Stint"].astype(float)

    # Build feature matrix
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
