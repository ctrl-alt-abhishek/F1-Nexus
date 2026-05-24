"""
app/ml/strategy/features.py - Feature engineering for pit stop strategy classifier.

Frames pit stop prediction as binary classification per lap:
  Label 1 = driver pitted on this lap (next lap's TyreLife resets to 1)
  Label 0 = no pit stop

Highly imbalanced dataset (~1 pit per 20 laps). scale_pos_weight in XGBoost handles this.
"""

import numpy as np
import pandas as pd

from app.ml.degradation.features import COMPOUND_MAP


def _add_predicted_deg(laps_df: pd.DataFrame, deg_model) -> pd.Series:
    """
    Use the degradation model to predict lap time for each row +3 laps ahead.
    This gives the strategy model a forward-looking signal.
    Returns a Series of predicted degradation deltas (positive = getting slower).
    """
    if deg_model is None:
        return pd.Series(0.0, index=laps_df.index)

    from app.ml.degradation.features import FEATURE_COLS

    # Build features for current lap
    total_laps = laps_df["LapNumber"].max()
    df = laps_df.copy()
    df["tire_age"] = df["TyreLife"].astype(float)
    df["compound_enc"] = df["Compound"].map(COMPOUND_MAP).fillna(1).astype(int)
    df["lap_number"] = df["LapNumber"].astype(float)
    df["fuel_proxy"] = 1.0 - (df["LapNumber"].astype(float) / max(total_laps, 1))
    driver_codes = sorted(df["Driver"].unique())
    driver_map = {code: idx for idx, code in enumerate(driver_codes)}
    df["driver_enc"] = df["Driver"].map(driver_map).astype(int)
    df["stint"] = df["Stint"].astype(float)
    df["track_temp_proxy"] = df["LapNumber"].astype(float) / 10.0
    df["round_enc"] = 0.0  # Unknown circuit fallback for degradation model inference

    # Features for +3 laps
    df_future = df.copy()
    df_future["tire_age"] = (df["TyreLife"] + 3).astype(float)
    df_future["lap_number"] = (df["LapNumber"] + 3).astype(float)
    df_future["fuel_proxy"] = 1.0 - ((df["LapNumber"] + 3).astype(float) / max(total_laps, 1))
    df_future["track_temp_proxy"] = (df["LapNumber"] + 3).astype(float) / 10.0

    try:
        current_pred = deg_model.predict(df[FEATURE_COLS])
        future_pred = deg_model.predict(df_future[FEATURE_COLS])
        return pd.Series(future_pred - current_pred, index=laps_df.index)
    except Exception:
        return pd.Series(0.0, index=laps_df.index)


def build_strategy_features(
    laps_df: pd.DataFrame,
    deg_model=None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build feature matrix and binary pit stop label.

    Input: cleaned laps DataFrame (same format as degradation model input).
    deg_model: trained degradation model (optional; enables predicted_deg feature).

    Features:
      tire_age          - TyreLife
      compound_enc      - Label encoded compound
      lap_number        - LapNumber
      fuel_proxy        - 1 - (LapNumber / total_laps)
      driver_enc        - Label encoded driver
      stint             - Stint number
      gap_ahead_s       - Approx gap to car ahead (0 if unavailable)
      predicted_deg     - Expected lap time increase over next 3 laps (from deg model)
      laps_remaining    - total_laps - lap_number
      current_position  - Position

    Target: pitted_this_lap (1 if pit on this lap, 0 otherwise)
    """
    df = laps_df.copy()
    total_laps = df["LapNumber"].max()

    # ── Reuse degradation features ───────────────────────────────────────────
    df["tire_age"] = df["TyreLife"].astype(float)
    df["compound_enc"] = df["Compound"].map(COMPOUND_MAP).fillna(1).astype(int)
    df["lap_number"] = df["LapNumber"].astype(float)
    df["fuel_proxy"] = 1.0 - (df["LapNumber"].astype(float) / max(total_laps, 1))

    driver_codes = sorted(df["Driver"].unique())
    driver_map = {code: idx for idx, code in enumerate(driver_codes)}
    df["driver_enc"] = df["Driver"].map(driver_map).astype(int)
    df["stint"] = df["Stint"].astype(float)

    # ── Strategy-specific features ───────────────────────────────────────────
    # Gap to car ahead - use GapToLeader proxy if direct gap not available
    if "GapAhead" in df.columns:
        df["gap_ahead_s"] = df["GapAhead"].fillna(0.0).astype(float)
    else:
        df["gap_ahead_s"] = 0.0

    # Forward-looking degradation signal from degradation model
    df["predicted_deg"] = _add_predicted_deg(df, deg_model)

    df["laps_remaining"] = (total_laps - df["LapNumber"]).astype(float)

    df["current_position"] = df["Position"].fillna(10).astype(float)

    # ── Target: did driver pit on this lap? ──────────────────────────────────
    # A pit is detected when the next lap's TyreLife resets to 1 (or ≤ 2)
    df_sorted = df.sort_values(["Driver", "LapNumber"])
    df_sorted["next_tyre_life"] = (
        df_sorted.groupby("Driver")["TyreLife"].shift(-1)
    )
    # Pit = next lap TyreLife is 1 or 2 AND current TyreLife > 2
    pitted = (
        (df_sorted["next_tyre_life"] <= 2) &
        (df_sorted["TyreLife"] > 2)
    ).astype(int)

    feature_cols = [
        "tire_age", "compound_enc", "lap_number", "fuel_proxy",
        "driver_enc", "stint", "gap_ahead_s", "predicted_deg",
        "laps_remaining", "current_position",
    ]

    # Drop rows with NaN target (last lap per driver has no "next" lap)
    valid_mask = df_sorted["next_tyre_life"].notna()
    X = df_sorted.loc[valid_mask, feature_cols].copy()
    y = pitted[valid_mask]

    return X, y


STRATEGY_FEATURE_COLS = [
    "tire_age", "compound_enc", "lap_number", "fuel_proxy",
    "driver_enc", "stint", "gap_ahead_s", "predicted_deg",
    "laps_remaining", "current_position",
]
