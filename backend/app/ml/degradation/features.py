"""
app/ml/degradation/features.py - Feature engineering for the tyre degradation model.

Key design decisions:
- fuel_proxy computed PER ROUND (not global) so lap 30/78 isn't confused with 30/57
- round_enc added as a feature so the model can distinguish circuit baseline lap times
- track_temp_proxy is lap_number / max_laps_in_round (0-1), not a global ratio
- Target is lap_time_s (absolute lap time in seconds) - circuit encoding handles baseline
"""

import pandas as pd
import numpy as np


# Compound encoding - consistent across all ML modules.
COMPOUND_MAP: dict[str, int] = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "INTER": 3,       # FastF1 sometimes uses abbreviated form
    "WET": 4,
}

FEATURE_COLS = [
    "tire_age",
    "compound_enc",
    "lap_number",
    "fuel_proxy",
    "driver_enc",
    "stint",
    "track_temp_proxy",
    "round_enc",        # NEW: encodes which circuit/round this lap is from
]


def build_features(laps_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build the feature matrix (X) and target vector (y) for degradation model training.

    Input: cleaned laps DataFrame from train_all.py (loaded from Neon).
    Expected columns: TyreLife, Compound, LapNumber, Driver, Stint, lap_time_s,
                      RoundNumber, Year.

    Features:
      tire_age         - TyreLife (int)
      compound_enc     - Label encoded compound (SOFT=0, MEDIUM=1, HARD=2, INTER=3, WET=4)
      lap_number       - LapNumber (int)
      fuel_proxy       - 1 - (LapNumber / max_laps_in_round) — PER-ROUND fuel proxy
      driver_enc       - Label encoded driver code (deterministic, sorted)
      stint            - Stint number (int)
      track_temp_proxy - lap_number / max_laps_in_round — track rubber/temp proxy
      round_enc        - Label encoded (Year * 100 + RoundNumber) — identifies circuit

    Target:
      lap_time_s       - Lap time in seconds (float)
    """
    df = laps_df.copy()

    # ── Compound ─────────────────────────────────────────────────────────────
    df["tire_age"] = df["TyreLife"].astype(float)
    df["compound_enc"] = df["Compound"].map(COMPOUND_MAP).fillna(1).astype(int)
    df["lap_number"] = df["LapNumber"].astype(float)
    df["stint"] = df["Stint"].astype(float)

    # ── Per-round fuel_proxy and track_temp_proxy ─────────────────────────────
    # Group by Year + RoundNumber so each race uses its own total lap count.
    # E.g., Monaco 2024 = 78 laps, Bahrain 2024 = 57 laps - computed separately.
    if "Year" in df.columns and "RoundNumber" in df.columns:
        round_key = df["Year"].astype(str) + "_" + df["RoundNumber"].astype(str)
        max_laps_per_round = df.groupby(round_key)["LapNumber"].transform("max")
    else:
        # Fallback: use global max (less accurate)
        max_laps_per_round = df["LapNumber"].max()

    max_laps_per_round = max_laps_per_round.replace(0, 1)  # avoid division by zero
    df["fuel_proxy"] = 1.0 - (df["LapNumber"].astype(float) / max_laps_per_round)
    df["track_temp_proxy"] = df["LapNumber"].astype(float) / max_laps_per_round

    # ── Driver encoding ───────────────────────────────────────────────────────
    driver_codes = sorted(df["Driver"].unique())
    driver_map = {code: idx for idx, code in enumerate(driver_codes)}
    df["driver_enc"] = df["Driver"].map(driver_map).astype(int)

    # ── Round encoding (identifies circuit) ───────────────────────────────────
    # Encode (Year, RoundNumber) as a single integer so the model knows which
    # circuit it's at. Without this, Monaco (75s) and Monza (81s) laps look identical.
    if "Year" in df.columns and "RoundNumber" in df.columns:
        round_keys = df["Year"].astype(int) * 100 + df["RoundNumber"].astype(int)
        unique_rounds = sorted(round_keys.unique())
        round_enc_map = {r: i for i, r in enumerate(unique_rounds)}
        df["round_enc"] = round_keys.map(round_enc_map).astype(int)
    else:
        df["round_enc"] = 0

    # ── Target ───────────────────────────────────────────────────────────────
    y = df["lap_time_s"].copy()

    valid_mask = y.notna() & df[FEATURE_COLS].notna().all(axis=1)
    X = df.loc[valid_mask, FEATURE_COLS].copy()
    y = y[valid_mask]

    return X, y


def get_driver_map(laps_df: pd.DataFrame) -> dict[str, int]:
    """
    Return the driver -> int encoding map for this dataset.
    Save alongside the model for consistent inference encodings.
    """
    driver_codes = sorted(laps_df["Driver"].unique())
    return {code: idx for idx, code in enumerate(driver_codes)}


def get_round_enc_map(laps_df: pd.DataFrame) -> dict[int, int]:
    """
    Return the (Year*100 + RoundNumber) -> int encoding map.
    Save alongside the model for consistent inference encodings.
    """
    if "Year" not in laps_df.columns or "RoundNumber" not in laps_df.columns:
        return {}
    round_keys = laps_df["Year"].astype(int) * 100 + laps_df["RoundNumber"].astype(int)
    unique_rounds = sorted(round_keys.unique())
    return {r: i for i, r in enumerate(unique_rounds)}
