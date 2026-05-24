"""
data/loader.py - FastF1 data fetching and caching utilities.
"""

import os
import fastf1
import pandas as pd


_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(_CACHE_DIR)


def get_session(year: int, round_number: int, session_type: str = "R"):
    session = fastf1.get_session(year, round_number, session_type)
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    return session


def get_race_laps(session) -> pd.DataFrame:
    laps = session.laps.copy()
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
    laps = laps.dropna(subset=["LapTimeSeconds", "Stint", "TyreLife"])

    median_time = laps["LapTimeSeconds"].median()
    laps = laps[laps["LapTimeSeconds"] <= median_time + 120]
    laps = laps[laps["PitOutTime"].isna() & laps["PitInTime"].isna()]
    laps = laps[laps["TrackStatus"] == "1"]
    laps = laps.reset_index(drop=True)

    return laps


def get_race_info(session) -> dict:
    event = session.event
    results = session.results

    race_name = event["EventName"]
    race_date = pd.Timestamp(event["EventDate"]).strftime("%B %d, %Y")

    winner_row = results[results["Position"] == 1.0]
    winner = winner_row["FullName"].values[0] if len(winner_row) > 0 else "N/A"

    pole_row = results[results["GridPosition"] == 1.0]
    pole_sitter = pole_row["FullName"].values[0] if len(pole_row) > 0 else "N/A"

    laps = session.laps.copy()
    laps["LapTimeSeconds"] = laps["LapTime"].dt.total_seconds()
    valid = laps.dropna(subset=["LapTimeSeconds"])
    if not valid.empty:
        fastest_idx = valid["LapTimeSeconds"].idxmin()
        fastest_driver = valid.loc[fastest_idx, "Driver"]
        fastest_time_s = valid.loc[fastest_idx, "LapTimeSeconds"]
        mins = int(fastest_time_s // 60)
        secs = fastest_time_s % 60
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
