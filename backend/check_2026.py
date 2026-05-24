import fastf1
from datetime import date
today = date.today()
print(f"Today: {today}")
print(f"FastF1 version: {fastf1.__version__}")
try:
    schedule = fastf1.get_event_schedule(2026, include_testing=False)
    print(f"Events in 2026: {len(schedule)}")
    for _, ev in schedule.iterrows():
        ed = ev.get("EventDate")
        if hasattr(ed, "date"):
            ed = ed.date()
        delta = (ed - today).days if ed else None
        marker = " <-- RACE WEEKEND" if delta is not None and -1 <= delta <= 3 else ""
        rn = ev.get("RoundNumber", "?")
        en = ev.get("EventName", "?")
        print(f"  Round {rn}: {en} | {ed} (delta={delta}){marker}")
except Exception as e:
    print(f"Error: {e}")
