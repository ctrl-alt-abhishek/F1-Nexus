"""
app/ml/strategy/predict.py - Pit stop window recommendation.
"""

import pandas as pd
import numpy as np

from app.ml.strategy.features import STRATEGY_FEATURE_COLS
from app.ml.degradation.features import COMPOUND_MAP


def recommend_pit_window(
    model,
    deg_model,
    current_lap: int,
    tire_age: int,
    compound: str,
    position: int,
    gap_ahead: float,
    total_laps: int,
    driver_enc: int = 0,
    stint: int = 1,
) -> dict:
    """
    Evaluate pit probability for the next 5 laps and return a recommendation.

    Returns:
        {
            'recommended_lap': int,
            'probabilities': [{'lap': int, 'pit_probability': float}, ...],
            'reasoning': str
        }
    """
    compound_enc = COMPOUND_MAP.get(compound.upper(), 1)
    laps_remaining_base = total_laps - current_lap

    rows = []
    for offset in range(5):
        future_lap = current_lap + offset
        future_tire_age = tire_age + offset
        fuel_proxy = 1.0 - (future_lap / max(total_laps, 1))
        laps_remaining = total_laps - future_lap

        # predicted_deg: approximate via linear extrapolation if deg_model provided
        predicted_deg = 0.0
        if deg_model is not None:
            from app.ml.degradation.features import FEATURE_COLS
            feat = pd.DataFrame([{
                "tire_age": float(future_tire_age),
                "compound_enc": float(compound_enc),
                "lap_number": float(future_lap),
                "fuel_proxy": fuel_proxy,
                "driver_enc": float(driver_enc),
                "stint": float(stint),
                "track_temp_proxy": float(future_lap) / 10.0,
                "round_enc": 0.0,  # Unknown circuit fallback
            }])
            feat_plus3 = feat.copy()
            feat_plus3["tire_age"] += 3
            feat_plus3["lap_number"] += 3
            try:
                curr_pred = deg_model.predict(feat[FEATURE_COLS])[0]
                fut_pred = deg_model.predict(feat_plus3[FEATURE_COLS])[0]
                predicted_deg = fut_pred - curr_pred
            except Exception:
                predicted_deg = 0.0

        rows.append({
            "tire_age": float(future_tire_age),
            "compound_enc": float(compound_enc),
            "lap_number": float(future_lap),
            "fuel_proxy": fuel_proxy,
            "driver_enc": float(driver_enc),
            "stint": float(stint),
            "gap_ahead_s": float(gap_ahead),
            "predicted_deg": predicted_deg,
            "laps_remaining": float(laps_remaining),
            "current_position": float(position),
        })

    X = pd.DataFrame(rows)[STRATEGY_FEATURE_COLS]
    probabilities = model.predict_proba(X)[:, 1]

    results = [
        {"lap": current_lap + i, "pit_probability": float(p)}
        for i, p in enumerate(probabilities)
    ]

    # Recommended lap = highest probability within the window
    best_idx = int(np.argmax(probabilities))
    recommended_lap = current_lap + best_idx
    best_prob = float(probabilities[best_idx])

    # Human-readable reasoning
    if best_prob > 0.7:
        urgency = "High urgency"
    elif best_prob > 0.4:
        urgency = "Moderate window"
    else:
        urgency = "No immediate need"

    reasoning = (
        f"{urgency} — pit probability {best_prob:.0%} on lap {recommended_lap}. "
        f"Tyre age {tire_age + best_idx} laps, {laps_remaining_base - best_idx} laps remaining."
    )

    return {
        "recommended_lap": recommended_lap,
        "probabilities": results,
        "reasoning": reasoning,
    }
