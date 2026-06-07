"""
app/services/schedule_utils.py - FastF1 schedule lookup utilities.
"""

import logging
from datetime import datetime, timezone, date
import fastf1
import pandas as pd
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def get_active_event() -> Optional[str]:
    """
    Check whether a live F1 timing session is currently running or within 
    the active weekend window (-1 to +3 days from event date).
    
    Returns the EventName if active, otherwise None.
    """
    try:
        today = date.today()
        schedule = fastf1.get_event_schedule(today.year, include_testing=False)

        for _, event in schedule.iterrows():
            event_date = event.get("EventDate")
            if event_date is None or event_date is pd.NaT:
                continue
                
            if hasattr(event_date, "date"):
                event_date = event_date.date()

            # Consider active if within 3 days before the race date
            delta = (event_date - today).days
            if -1 <= delta <= 3:
                logger.info(
                    "Race weekend detected: %s (race date: %s)",
                    event.get("EventName", "?"),
                    event_date,
                )
                return str(event.get("EventName", ""))

    except Exception as exc:
        logger.debug("Session check failed (normal off-weekend): %s", exc)

    return None

def get_next_race_info() -> Optional[Dict[str, Any]]:
    """
    Get the name, location, date, and timing of the next upcoming race.
    """
    try:
        now = datetime.now(timezone.utc)
        
        # Get event schedule for current year
        schedule = fastf1.get_event_schedule(now.year, include_testing=False)
        
        future_events = []
        for _, ev in schedule.iterrows():
            race_date = ev.get("Session5DateUtc")
            if race_date is not pd.NaT and race_date is not None:
                dt = race_date.to_pydatetime().replace(tzinfo=timezone.utc)
                if dt >= now:
                    future_events.append((dt, ev))
        
        if not future_events:
            # Fallback to next year if we are at the end of the season
            schedule = fastf1.get_event_schedule(now.year + 1, include_testing=False)
            for _, ev in schedule.iterrows():
                race_date = ev.get("Session5DateUtc")
                if race_date is not pd.NaT and race_date is not None:
                    dt = race_date.to_pydatetime().replace(tzinfo=timezone.utc)
                    if dt >= now:
                        future_events.append((dt, ev))
        
        if future_events:
            future_events.sort(key=lambda x: x[0])
            next_dt, next_ev = future_events[0]
            
            loc = next_ev.get("Location", "")
            if isinstance(loc, str):
                loc = loc.encode("utf-8", "ignore").decode("utf-8")
            
            country = next_ev.get("Country", "")
            
            time_str_utc = next_dt.strftime("%H:%M UTC")
            date_str = next_dt.strftime("%B %d, %Y")
            
            return {
                "name": next_ev.get("EventName"),
                "location": loc,
                "country": country,
                "date": date_str,
                "time": time_str_utc,
                "session_type": "Race"
            }
    except Exception as e:
        logger.exception("Failed to get next race info")
    return None

def get_event_details(event_name: str) -> tuple[str, str, str]:
    """
    Given an event name, fetch its EventName, Location, and Country from the schedule.
    Returns (race_name, location, country).
    """
    race_name, location, country = event_name, "", ""
    try:
        schedule = fastf1.get_event_schedule(datetime.now().year, include_testing=False)
        for _, event in schedule.iterrows():
            if event.get("EventName") == event_name:
                race_name = event.get("EventName")
                location = event.get("Location")
                country = event.get("Country")
                break
    except Exception as e:
        logger.debug("Failed to populate active event details: %s", e)
    return str(race_name), str(location), str(country)
