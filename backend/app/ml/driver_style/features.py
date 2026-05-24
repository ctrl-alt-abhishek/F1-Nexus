"""
app/ml/driver_style/features.py - Per-driver driving style feature extraction from telemetry.

Extracts corner-by-corner braking, throttle, and speed characteristics.
Telemetry loading is SLOW (~2-5 min per session) - only used for offline style profiling,
never called during live API serving.
"""

import logging
import numpy as np
import pandas as pd
import fastf1

logger = logging.getLogger(__name__)


def extract_style_features(
    session: fastf1.core.Session,
    driver_code: str,
) -> dict:
    """
    Extract driving style features for a single driver in a session.

    Loads telemetry (required for this module - different from fastf1_loader which
    skips telemetry for speed). Analyzes each corner on the circuit:
      - min_speed_corner:       minimum speed through each corner
      - braking_point_dist:     distance from corner apex where braking starts
      - throttle_application:   distance from apex where full throttle applied
      - max_lateral_g:          peak lateral G (cornering aggression proxy)

    Aggregates to circuit-level stats (avg + std of each).

    Returns flat dict of floats, or empty dict if telemetry unavailable.
    """
    try:
        # Load telemetry only for this specific driver's fastest lap
        laps = session.laps.pick_driver(driver_code)
        if laps.empty:
            logger.warning("No laps found for driver %s", driver_code)
            return {}

        fastest_lap = laps.pick_fastest()
        if fastest_lap is None or fastest_lap.empty:
            return {}

        tel = fastest_lap.get_telemetry()
        if tel is None or tel.empty:
            return {}

        # ── Corner detection via speed minima ────────────────────────────────
        # Find local speed minima as corner apexes
        speed = tel["Speed"].values
        distance = tel["Distance"].values

        # Simple local minima detection with window
        corner_indices = _find_speed_minima(speed, window=20, threshold_pct=0.85)

        if len(corner_indices) == 0:
            return _fallback_features(tel)

        # ── Per-corner analysis ───────────────────────────────────────────────
        min_speeds = []
        braking_dists = []
        throttle_dists = []
        lateral_gs = []

        throttle = tel["Throttle"].values if "Throttle" in tel.columns else np.ones(len(tel))
        brake = tel["Brake"].values if "Brake" in tel.columns else np.zeros(len(tel))

        for apex_idx in corner_indices:
            apex_dist = distance[apex_idx]
            min_speeds.append(float(speed[apex_idx]))

            # Braking point: last point before apex where brake first applied
            search_start = max(0, apex_idx - 50)
            braking_point = apex_idx
            for i in range(apex_idx, search_start, -1):
                if brake[i] > 0.5:
                    braking_point = i
                    break
            braking_dists.append(float(apex_dist - distance[braking_point]))

            # Throttle application: first full throttle after apex
            search_end = min(len(tel) - 1, apex_idx + 50)
            throttle_point = apex_idx
            for i in range(apex_idx, search_end):
                if throttle[i] > 90:  # >90% throttle = full throttle
                    throttle_point = i
                    break
            throttle_dists.append(float(distance[throttle_point] - apex_dist))

            # Lateral G around corner (if available)
            if "nGLat" in tel.columns:
                corner_slice = tel["nGLat"].iloc[
                    max(0, apex_idx - 10):min(len(tel), apex_idx + 10)
                ].abs()
                lateral_gs.append(float(corner_slice.max()) if not corner_slice.empty else 0.0)

        features = {
            "avg_corner_speed": float(np.mean(min_speeds)) if min_speeds else 0.0,
            "std_corner_speed": float(np.std(min_speeds)) if min_speeds else 0.0,
            "avg_braking_point_dist": float(np.mean(braking_dists)) if braking_dists else 0.0,
            "std_braking_point_dist": float(np.std(braking_dists)) if braking_dists else 0.0,
            "avg_throttle_dist": float(np.mean(throttle_dists)) if throttle_dists else 0.0,
            "std_throttle_dist": float(np.std(throttle_dists)) if throttle_dists else 0.0,
            "avg_max_lateral_g": float(np.mean(lateral_gs)) if lateral_gs else 0.0,
            "num_corners": float(len(corner_indices)),
        }

        return features

    except Exception as e:
        logger.warning("Could not extract style features for %s: %s", driver_code, e)
        return {}


def build_style_matrix(sessions: list, driver_codes: list) -> pd.DataFrame:
    """
    Build a driver style feature matrix across multiple sessions.

    Args:
        sessions:     list of loaded FastF1 Session objects (with telemetry)
        driver_codes: list of driver codes to include

    Returns:
        DataFrame with driver_code as index and style features as columns.
        Rows with missing data are dropped.
    """
    records = []
    for session in sessions:
        for driver_code in driver_codes:
            features = extract_style_features(session, driver_code)
            if features:
                features["driver_code"] = driver_code
                features["session"] = f"{session.event.year}_{session.event.RoundNumber}"
                records.append(features)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # Average across sessions per driver
    numeric_cols = [c for c in df.columns if c not in ("driver_code", "session")]
    style_matrix = df.groupby("driver_code")[numeric_cols].mean()

    return style_matrix


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_speed_minima(speed: np.ndarray, window: int = 20, threshold_pct: float = 0.85) -> list:
    """Find indices of local speed minima (corner apexes)."""
    minima = []
    n = len(speed)
    speed_threshold = speed.max() * threshold_pct

    for i in range(window, n - window):
        if speed[i] > speed_threshold:
            continue  # not slow enough to be a corner
        local_min = speed[max(0, i - window):i + window].min()
        if speed[i] <= local_min * 1.01:  # within 1% of local minimum
            if not minima or i - minima[-1] > window:  # avoid duplicates
                minima.append(i)

    return minima


def _fallback_features(tel: pd.DataFrame) -> dict:
    """Return basic features from telemetry when corner detection fails."""
    features = {
        "avg_corner_speed": float(tel["Speed"].quantile(0.1)) if "Speed" in tel.columns else 0.0,
        "std_corner_speed": float(tel["Speed"].std()) if "Speed" in tel.columns else 0.0,
        "avg_braking_point_dist": 0.0,
        "std_braking_point_dist": 0.0,
        "avg_throttle_dist": 0.0,
        "std_throttle_dist": 0.0,
        "avg_max_lateral_g": 0.0,
        "num_corners": 0.0,
    }
    return features


STYLE_FEATURE_COLS = [
    "avg_corner_speed",
    "std_corner_speed",
    "avg_braking_point_dist",
    "std_braking_point_dist",
    "avg_throttle_dist",
    "std_throttle_dist",
    "avg_max_lateral_g",
    "num_corners",
]
