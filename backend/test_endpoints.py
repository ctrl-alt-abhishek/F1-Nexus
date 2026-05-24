import urllib.request, json

tests = [
    ("Health", "http://localhost:8000/health"),
    ("Races 2024", "http://localhost:8000/api/v1/races/2024"),
    ("Race Analysis 2024/5", "http://localhost:8000/api/v1/races/2024/5"),
    ("Drivers 2024", "http://localhost:8000/api/v1/drivers?year=2024"),
    ("Driver VER", "http://localhost:8000/api/v1/drivers/VER"),
    ("Live Status", "http://localhost:8000/api/v1/live/status"),
    ("Championship 2024", "http://localhost:8000/api/v1/predictions/championship/2024"),
    ("Pit Window", "http://localhost:8000/api/v1/predictions/pit-window?round_id=1&driver_code=VER&current_lap=20&tire_age=15&compound=MEDIUM&position=1"),
    ("Laps Paginated", "http://localhost:8000/api/v1/races/2024/1/laps?driver_code=VER&page=1&page_size=5"),
]

for name, url in tests:
    try:
        r = urllib.request.urlopen(url, timeout=30)
        data = json.loads(r.read())
        
        if name == "Health":
            print(f"[PASS] {name}: {data}")
        elif name == "Races 2024":
            print(f"[PASS] {name}: {len(data)} rounds")
        elif name == "Race Analysis 2024/5":
            winner = data.get("winner_code")
            total = data.get("total_laps")
            stints = len(data.get("tire_stints", []))
            curves = list(data.get("degradation_curves", {}).keys())
            print(f"[PASS] {name}: winner={winner}, laps={total}, stints={stints}, curves={curves}")
        elif name == "Drivers 2024":
            print(f"[PASS] {name}: {len(data)} drivers")
        elif name == "Driver VER":
            d = data.get("driver", {})
            s = data.get("career_stats", {})
            print(f"[PASS] {name}: {d.get('full_name')}, {d.get('team')}, wins={s.get('wins')}, races={s.get('races')}")
        elif name == "Live Status":
            print(f"[PASS] {name}: active={data.get('active')}")
        elif name == "Championship 2024":
            drivers = data.get("drivers", [])
            top = drivers[0] if drivers else {}
            print(f"[PASS] {name}: {len(drivers)} drivers, top={top.get('driver_code')} ({top.get('championship_probability',0):.1%})")
        elif name == "Pit Window":
            print(f"[PASS] {name}: recommended_lap={data.get('recommended_lap')}, reasoning={data.get('reasoning','')[:80]}")
        elif name == "Laps Paginated":
            print(f"[PASS] {name}: {data.get('total')} total, page {data.get('page')}, showing {len(data.get('items',[]))} items")
        else:
            print(f"[PASS] {name}: OK")
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        print(f"[FAIL] {name}: HTTP {e.code} — {body}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
