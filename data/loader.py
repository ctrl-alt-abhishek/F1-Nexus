"""
data/loader.py
FastF1 data fetching and caching utilities.
"""

import os
import fastf1
import pandas as pd


# Enable FastF1 cache at startup
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(_CACHE_DIR)


def get_session(year: int, round_number: int, session_type: str = "R"):
    """
    Load and return a FastF1 session.

    Parameters
    ----------
    year : int
        Season year (e.g. 2024).
    round_number : int
        Round number in the calendar (1-22).
    session_type : str
        Session identifier, default 'R' for Race.

    Returns
    -------
    fastf1.core.Session
    """
    session = fastf1.get_session(year, round_number, session_type)
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    return session


def get_race_laps(session) -> pd.DataFrame:
    """
    Return a cleaned DataFrame of valid racing laps from the session.

    Filtering rules:
    - Drop laps where LapTime is NaN
    - Drop laps where LapTime > 120 seconds above the session median
    - Drop pit in/out laps (PitOutTime or PitInTime is not NaN)
    - Drop laps where TrackStatus != '1' (safety car, VSC, red flag)
    """
    laps = session.laps.copy()

    # Convert LapTime timedelta to seconds
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()

    # Drop NaN lap times, stint, or tyre life
    laps = laps.dropna(subset=["LapTimeSeconds", "Stint", "TyreLife"])

    # Drop outlier lap times (> 120s above median)
    median_time = laps["LapTimeSeconds"].median()
    laps = laps[laps["LapTimeSeconds"] <= median_time + 120]

    # Drop pit in/out laps
    laps = laps[laps["PitOutTime"].isna() & laps["PitInTime"].isna()]

    # Keep only green flag laps (TrackStatus == '1')
    laps = laps[laps["TrackStatus"] == "1"]

    # Reset index
    laps = laps.reset_index(drop=True)

    return laps


def get_race_info(session) -> dict:
    """
    Extract key race metadata from a loaded session.

    Returns
    -------
    dict with keys:
        'race_name'    : str, official event name
        'date'         : str, event date formatted as readable string
        'winner'       : str, full name of the race winner
        'pole_sitter'  : str, full name of the pole position holder
        'fastest_lap'  : str, full name of the fastest lap holder + time
    """
    event = session.event
    results = session.results

    # Race name and date
    race_name = event["EventName"]
    race_date = pd.Timestamp(event["EventDate"]).strftime("%B %d, %Y")

    # Winner = Position 1
    winner_row = results[results["Position"] == 1.0]
    winner = winner_row["FullName"].values[0] if len(winner_row) > 0 else "N/A"

    # Pole sitter = GridPosition 1
    pole_row = results[results["GridPosition"] == 1.0]
    pole_sitter = pole_row["FullName"].values[0] if len(pole_row) > 0 else "N/A"

    # Fastest lap = pick from laps data
    laps = session.laps.copy()
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
    valid = laps.dropna(subset=["LapTimeSeconds"])
    if not valid.empty:
        fastest_idx = valid["LapTimeSeconds"].idxmin()
        fastest_driver = valid.loc[fastest_idx, "Driver"]
        fastest_time_s = valid.loc[fastest_idx, "LapTimeSeconds"]
        mins = int(fastest_time_s // 60)
        secs = fastest_time_s % 60
        # Map abbreviation to full name from results
        fl_row = results[results["Abbreviation"] == fastest_driver]
        fl_name = fl_row["FullName"].values[0] if len(fl_row) > 0 else fastest_driver
        fastest_lap = f"{fl_name} ({mins}:{secs:06.3f})"
    else:
        fastest_lap = "N/A"

    return {
        "race_name": race_name,
        "date": race_date,
        "winner": winner,
        "pole_sitter": pole_sitter,
        "fastest_lap": fastest_lap,
    }
