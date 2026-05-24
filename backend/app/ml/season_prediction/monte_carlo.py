"""
app/ml/season_prediction/monte_carlo.py - Championship probability via Monte Carlo simulation.

Simulates the remaining races of the season N=10,000 times.
Each simulation samples from a per-driver Gaussian performance distribution
calibrated on their recent finishing positions.

This is deliberately a statistical model, not ML - no training required.
Run on demand via predictions router and cached in-memory.
"""

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


# F1 2024 points system
POINTS_SYSTEM = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}
N_SIMULATIONS = 10_000


def _get_current_standings(db: Session, year: int) -> pd.DataFrame:
    """
    Get current driver standings for the season from the DB.
    Returns DataFrame with columns: driver_code, full_name, team, points_so_far, races_completed.
    """
    result = db.execute(text("""
        SELECT
            d.code AS driver_code,
            d.full_name,
            c.name AS team,
            COALESCE(SUM(rr.points), 0) AS points_so_far,
            COUNT(rr.id) AS races_completed
        FROM drivers d
        JOIN driver_season ds ON ds.driver_code = d.code AND ds.season_year = :year
        LEFT JOIN constructors c ON c.id = ds.constructor_id
        LEFT JOIN rounds r ON r.season_year = :year
        LEFT JOIN race_results rr ON rr.driver_code = d.code AND rr.round_id = r.id
        GROUP BY d.code, d.full_name, c.name
        ORDER BY points_so_far DESC
    """), {"year": year})
    return pd.DataFrame(result.fetchall(), columns=result.keys())


def _get_recent_results(db: Session, year: int, last_n: int = 5) -> pd.DataFrame:
    """
    Get each driver's finishing positions in their last N races.
    Used to calibrate per-driver performance distribution.
    Blends the current season with the previous season (e.g. 2024) to handle
    early-season prediction instability gracefully.
    """
    result = db.execute(text("""
        SELECT
            rr.driver_code,
            rr.finish_position,
            r.season_year,
            r.round_number
        FROM race_results rr
        JOIN rounds r ON r.id = rr.round_id
        WHERE r.season_year <= :year
          AND rr.finish_position IS NOT NULL
        ORDER BY r.season_year DESC, r.round_number DESC
    """), {"year": year})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())

    # Take last N per driver
    return df.groupby("driver_code").head(last_n)


def simulate_season(
    db: Session,
    year: int,
    total_rounds: int = 24,
    profile: str = "balanced",
    seed: int | None = 42,
) -> list[dict]:
    """
    Run Monte Carlo championship simulation.

    Args:
        year:         Season year
        total_rounds: Total races in the season (used to compute remaining races)
        profile:      'balanced' | 'aggressive' | 'conservative'
                      Changes standard deviation of the performance sampling.
    Returns:
        List of dicts sorted by championship_probability descending:
        [
            {
                'driver_code':                str,
                'full_name':                  str,
                'team':                       str,
                'current_points':             float,
                'championship_probability':   float (0-1),
                'podium_probability':         float (0-1),
                'expected_final_points':      float,
            },
            ...
        ]
    """
    standings = _get_current_standings(db, year)
    recent = _get_recent_results(db, year, last_n=5)

    if standings.empty:
        return []

    drivers = standings["driver_code"].tolist()
    current_points = {
        row.driver_code: float(row.points_so_far)
        for row in standings.itertuples()
    }
    name_map = {row.driver_code: row.full_name for row in standings.itertuples()}
    team_map = {row.driver_code: row.team for row in standings.itertuples()}

    # Races already completed = max round_number in results
    races_done = int(standings["races_completed"].max()) if not standings.empty else 0
    races_remaining = max(0, total_rounds - races_done)

    if races_remaining == 0:
        # Season complete - championship is determined
        champion = standings.iloc[0]["driver_code"]
        return [
            {
                "driver_code": row.driver_code,
                "full_name": row.full_name,
                "team": row.team,
                "current_points": float(row.points_so_far),
                "championship_probability": 1.0 if row.driver_code == champion else 0.0,
                "podium_probability": 1.0 if row.driver_code in standings.head(3)["driver_code"].tolist() else 0.0,
                "expected_final_points": float(row.points_so_far),
            }
            for row in standings.itertuples()
        ]

    # ── Build per-driver performance distribution ─────────────────────────────
    # Mean finishing position from recent results (lower = better)
    # Drivers with no results get mean=10.5 (midfield)
    driver_perf = {}
    for driver in drivers:
        d_recent = recent[recent["driver_code"] == driver]["finish_position"]
        if not d_recent.empty:
            n_obs = len(d_recent)
            mean_val = float(d_recent.mean())
            # Regress towards midfield (10.5) with a weight of 3 races
            # This handles low sample sizes (e.g. at the start of a season or for rookies)
            prior_weight = 3.0
            regressed_mean = (mean_val * n_obs + 10.5 * prior_weight) / (n_obs + prior_weight)

            # Estimate standard deviation, fallback to 4.0 if not enough points
            std_val = float(d_recent.std()) if n_obs > 1 else 4.0
            if pd.isna(std_val):
                std_val = 4.0

            driver_perf[driver] = {
                "mean_pos": regressed_mean,
                "std_pos": max(std_val, 3.5), # Minimum standard deviation of 3.5 to model F1 variance
            }
        else:
            driver_perf[driver] = {"mean_pos": 10.5, "std_pos": 4.5}

    # Profile-based noise scaling
    std_multiplier = {"balanced": 1.0, "aggressive": 1.5, "conservative": 0.7}.get(profile, 1.0)

    # ── Monte Carlo simulation ─────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    championship_wins = np.zeros(len(drivers))
    podium_counts = np.zeros(len(drivers))
    total_points_sum = np.zeros(len(drivers))

    n_drivers = len(drivers)

    for _ in range(N_SIMULATIONS):
        sim_points = np.array([current_points.get(d, 0.0) for d in drivers])

        for _race in range(races_remaining):
            # Sample finishing positions for all drivers simultaneously
            sampled_positions = []
            for d in drivers:
                perf = driver_perf[d]
                pos = rng.normal(perf["mean_pos"], perf["std_pos"] * std_multiplier)
                pos = max(1.0, min(n_drivers, pos))
                sampled_positions.append(pos)

            # Rank by sampled position (lower pos = better = more points)
            order = np.argsort(sampled_positions)
            for rank, driver_idx in enumerate(order):
                finish_pos = rank + 1
                pts = POINTS_SYSTEM.get(finish_pos, 0)
                sim_points[driver_idx] += pts

        # Record outcomes
        champion_idx = int(np.argmax(sim_points))
        championship_wins[champion_idx] += 1

        top3_idx = np.argsort(sim_points)[-3:]
        for idx in top3_idx:
            podium_counts[idx] += 1

        total_points_sum += sim_points

    # ── Build output ─────────────────────────────────────────────────────────
    output = []
    for i, driver in enumerate(drivers):
        output.append({
            "driver_code": driver,
            "full_name": name_map.get(driver, driver),
            "team": team_map.get(driver, ""),
            "current_points": current_points.get(driver, 0.0),
            "championship_probability": float(championship_wins[i] / N_SIMULATIONS),
            "podium_probability": float(podium_counts[i] / N_SIMULATIONS),
            "expected_final_points": float(total_points_sum[i] / N_SIMULATIONS),
        })

    output.sort(key=lambda x: x["championship_probability"], reverse=True)
    return output
