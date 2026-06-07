"""
app/services/simulation.py - Live timing simulation and synthetic mock.
"""

import asyncio
import logging
from datetime import datetime, timezone
import random

from app.config import settings

logger = logging.getLogger(__name__)

async def run_simulation_client(worker) -> None:
    """
    Simulation fallback when SignalRClient is unavailable.
    Loads laps of a matching or default historical race from database,
    and streams them to all registered clients.
    """
    logger.info("Starting live timing simulation...")
    
    from app.database import get_db_context
    from sqlalchemy import text
    
    rnd_id = None
    rnd_name = "Simulated Race"
    
    try:
        with get_db_context() as db:
            active_name = getattr(worker, "_active_event_name", None) or "Canada"
            
            # Try to find a seeded round matching the active name
            row = db.execute(
                text("SELECT id, name FROM rounds WHERE name ILIKE :name LIMIT 1"),
                {"name": f"%{active_name}%"}
            ).fetchone()
            
            if not row:
                # Try to find any round with lap data
                row = db.execute(
                    text("""
                        SELECT r.id, r.name FROM rounds r
                        JOIN laps l ON l.round_id = r.id
                        GROUP BY r.id, r.name
                        LIMIT 1
                    """)
                ).fetchone()
            
            if row:
                rnd_id = row[0]
                rnd_name = row[1]
                logger.info("Simulation using round data from %s (ID: %d)", rnd_name, rnd_id)
    except Exception:
        logger.exception("Failed to query round for simulation")
        
    if not rnd_id:
        logger.warning("No rounds found in DB for simulation. Running purely synthetic mock.")
        await run_synthetic_mock(worker)
        return

    try:
        with get_db_context() as db:
            # Query laps
            laps_rows = db.execute(
                text("""
                    SELECT driver_code, lap_number, lap_time_s, sector1_s, sector2_s, sector3_s,
                           compound, tyre_life, stint, position, track_status
                    FROM laps
                    WHERE round_id = :round_id
                    ORDER BY lap_number, position
                """),
                {"round_id": rnd_id}
            ).fetchall()
            
            # Query driver list for encoding
            driver_rows = db.execute(text("SELECT DISTINCT driver_code FROM laps")).fetchall()
            driver_codes = sorted([r[0] for r in driver_rows])
            driver_map = {code: idx for idx, code in enumerate(driver_codes)}
            
            # Query round data for encoding
            round_rows = db.execute(
                text("SELECT season_year, round_number FROM rounds WHERE id = :round_id"),
                {"round_id": rnd_id}
            ).fetchone()
            
            if round_rows:
                year, round_number = round_rows
                round_key = year * 100 + round_number
                all_rounds = db.execute(text("SELECT DISTINCT season_year, round_number FROM rounds")).fetchall()
                unique_keys = sorted([yr[0] * 100 + yr[1] for yr in all_rounds])
                round_enc_map = {rk: idx for idx, rk in enumerate(unique_keys)}
                round_enc = round_enc_map.get(round_key, 0)
            else:
                round_enc = 0
    except Exception:
        logger.exception("Failed to load laps from DB for simulation")
        await run_synthetic_mock(worker)
        return
        
    if not laps_rows:
        logger.warning("No laps found for round %d. Running purely synthetic mock.", rnd_id)
        await run_synthetic_mock(worker)
        return
        
    from collections import defaultdict
    laps_by_num = defaultdict(list)
    for row in laps_rows:
        driver_code, lap_num, lap_time_s, s1, s2, s3, compound, tyre_life, stint, position, track_status = row
        laps_by_num[lap_num].append({
            "driver_code": driver_code,
            "lap_time_s": lap_time_s,
            "s1": s1,
            "s2": s2,
            "s3": s3,
            "compound": compound,
            "tyre_life": tyre_life,
            "stint": stint,
            "position": position,
            "track_status": track_status
        })
        
    max_laps = max(laps_by_num.keys())
    logger.info("Starting simulation of %s: %d laps, %d laps loaded", rnd_name, max_laps, len(laps_rows))
    
    active_name = getattr(worker, "_active_event_name", None) or rnd_name or "Canada"
    race_name, location, country = active_name, "", ""
    try:
        import fastf1
        schedule = fastf1.get_event_schedule(datetime.now().year, include_testing=False)
        for _, event in schedule.iterrows():
            if event.get("EventName") == active_name or event.get("EventName") == rnd_name:
                race_name = event.get("EventName")
                location = event.get("Location")
                country = event.get("Country")
                break
    except Exception as e:
        logger.debug("Failed to populate active event details: %s", e)

    async with worker._lock:
        worker._state["active"] = True
        worker._state["session_type"] = "Race"
        worker._state["current_lap"] = 0
        worker._state["drivers"] = {}
        worker._state["race_name"] = race_name
        worker._state["location"] = location
        worker._state["country"] = country
        worker._prev_tyre_life = {}
        worker._fastest_lap_s = float("inf")
        
    cumulative_times = {}
    
    for lap_num in range(1, max_laps + 1):
        if not worker._running:
            break
            
        async with worker._lock:
            if not worker._state["active"]:
                break
        
        lap_data = laps_by_num[lap_num]
        if not lap_data:
            await asyncio.sleep(2)
            continue
            
        logger.info("Simulating Lap %d/%d...", lap_num, max_laps)
        
        if lap_num == 1:
            asyncio.create_task(worker._notify_race_start())
            
        for lap_record in lap_data:
            code = lap_record["driver_code"]
            lap_s = lap_record["lap_time_s"] or 90.0
            cumulative_times[code] = cumulative_times.get(code, 0.0) + lap_s
            
        sorted_drivers = sorted(cumulative_times.keys(), key=lambda c: cumulative_times[c])
        leader_code = sorted_drivers[0]
        leader_time = cumulative_times[leader_code]
        
        next_lap_data_by_driver = {}
        if lap_num < max_laps:
            for next_rec in laps_by_num[lap_num + 1]:
                next_lap_data_by_driver[next_rec["driver_code"]] = next_rec

        safety_car_deployed = False
        for lap_record in lap_data:
            ts = str(lap_record["track_status"] or "1")
            if ts in ("4", "5"):
                safety_car_deployed = True
                break
                
        if safety_car_deployed:
            asyncio.create_task(worker._notify_safety_car(lap_num))

        from app.ml.loader import models
        from app.ml.strategy.predict import recommend_pit_window
        
        async with worker._lock:
            worker._state["current_lap"] = lap_num
            
            for idx, code in enumerate(sorted_drivers):
                lap_record = next((r for r in lap_data if r["driver_code"] == code), None)
                if not lap_record:
                    continue
                    
                pos = idx + 1
                gap_to_leader = cumulative_times[code] - leader_time
                gap_ahead = 0.0 if idx == 0 else cumulative_times[code] - cumulative_times[sorted_drivers[idx - 1]]
                
                compound = lap_record["compound"]
                tyre_life = lap_record["tyre_life"] or 1
                stint = lap_record["stint"] or 1
                lap_time_s = lap_record["lap_time_s"]
                
                pitting = False
                next_rec = next_lap_data_by_driver.get(code)
                if next_rec:
                    next_tyre_life = next_rec["tyre_life"] or 1
                    next_stint = next_rec["stint"] or 1
                    if (next_tyre_life <= 2 and tyre_life > 2) or (next_stint > stint):
                        pitting = True
                        
                if pitting:
                    asyncio.create_task(worker._notify_pit_stop(code, next_rec["compound"] or "MEDIUM"))
                    
                if lap_time_s and 0 < lap_time_s < worker._fastest_lap_s:
                    worker._fastest_lap_s = lap_time_s
                    asyncio.create_task(worker._notify_fastest_lap(code, lap_time_s))
                    
                predicted_stint_end = None
                if models.strategy is not None and models.degradation is not None:
                    try:
                        driver_enc = driver_map.get(code, 0)
                        pred_res = recommend_pit_window(
                            models.strategy,
                            models.degradation,
                            current_lap=lap_num,
                            tire_age=tyre_life,
                            compound=compound or "MEDIUM",
                            position=pos,
                            gap_ahead=gap_ahead,
                            total_laps=max_laps,
                            driver_enc=driver_enc,
                            stint=stint,
                        )
                        predicted_stint_end = pred_res["recommended_lap"]
                    except Exception as e:
                        logger.debug("Failed to recommend pit window in simulation: %s", e)
                        
                worker._state["drivers"][code] = {
                    "code": code,
                    "position": pos,
                    "gap_to_leader": gap_to_leader,
                    "compound": compound,
                    "tyre_life": tyre_life,
                    "predicted_stint_end": predicted_stint_end,
                    "last_lap_s": lap_time_s,
                    "sector1_s": lap_record["s1"],
                    "sector2_s": lap_record["s2"],
                    "sector3_s": lap_record["s3"],
                    "drs": (gap_ahead < 1.0 and lap_num > 2 and idx > 0),
                    "pitting": pitting,
                }
                
        timestamp = datetime.now(timezone.utc).isoformat()
        await worker._broadcast_state(timestamp)
        await asyncio.sleep(2.0)
        
    async with worker._lock:
        worker._state["active"] = False
        worker._state["drivers"] = {}
        worker._state["race_name"] = None
        worker._state["location"] = None
        worker._state["country"] = None
    logger.info("Simulation finished.")

async def run_synthetic_mock(worker) -> None:
    """Purely synthetic simulation when no rounds are in DB."""
    logger.info("Running synthetic live timing mock...")
    drivers_list = ["VER", "HAM", "NOR", "LEC", "SAI", "PIA", "RUS", "PER", "ALO", "STR"]
    
    async with worker._lock:
        worker._state["active"] = True
        worker._state["session_type"] = "Race"
        worker._state["current_lap"] = 0
        worker._state["drivers"] = {}
        worker._state["race_name"] = "Mock Grand Prix"
        worker._state["location"] = "Mock Location"
        worker._state["country"] = "Mock Country"
        
    driver_states = {}
    for idx, code in enumerate(drivers_list):
        driver_states[code] = {
            "code": code,
            "position": idx + 1,
            "gap_to_leader": idx * 1.5,
            "compound": "MEDIUM" if idx % 2 == 0 else "HARD",
            "tyre_life": random.randint(1, 10),
            "predicted_stint_end": 20 + random.randint(1, 5),
            "last_lap_s": 85.0 + idx * 0.1,
            "sector1_s": 28.1,
            "sector2_s": 29.3,
            "sector3_s": 27.6,
            "drs": False,
            "pitting": False,
        }
        
    max_laps = 50
    for lap_num in range(1, max_laps + 1):
        if not worker._running:
            break
            
        async with worker._lock:
            if not worker._state["active"]:
                break
                
            worker._state["current_lap"] = lap_num
            
            if lap_num == 1:
                asyncio.create_task(worker._notify_race_start())
                
            for idx, code in enumerate(drivers_list):
                ds = driver_states[code]
                ds["tyre_life"] += 1
                
                base_lap = 84.0 + (ds["tyre_life"] * 0.05)
                lap_time_s = base_lap + random.uniform(-0.5, 0.5)
                ds["last_lap_s"] = lap_time_s
                ds["sector1_s"] = lap_time_s * 0.33
                ds["sector2_s"] = lap_time_s * 0.34
                ds["sector3_s"] = lap_time_s * 0.33
                
                pitting = False
                if ds["tyre_life"] > 18 + random.randint(0, 5):
                    pitting = True
                    
                if pitting:
                    ds["compound"] = "SOFT" if ds["compound"] == "HARD" else "MEDIUM"
                    ds["tyre_life"] = 1
                    asyncio.create_task(worker._notify_pit_stop(code, ds["compound"]))
                    
                ds["pitting"] = pitting
                
            if random.random() < 0.15:
                swap_idx = random.randint(1, len(drivers_list) - 1)
                drivers_list[swap_idx], drivers_list[swap_idx - 1] = drivers_list[swap_idx - 1], drivers_list[swap_idx]
                
            for idx, code in enumerate(drivers_list):
                ds = driver_states[code]
                ds["position"] = idx + 1
                ds["gap_to_leader"] = idx * 1.2 + random.uniform(-0.2, 0.2)
                ds["drs"] = idx > 0 and (ds["gap_to_leader"] - driver_states[drivers_list[idx - 1]]["gap_to_leader"] < 1.0)
                
                worker._state["drivers"][code] = dict(ds)
                
        timestamp = datetime.now(timezone.utc).isoformat()
        await worker._broadcast_state(timestamp)
        await asyncio.sleep(2.0)
        
    async with worker._lock:
        worker._state["active"] = False
        worker._state["drivers"] = {}
        worker._state["race_name"] = None
        worker._state["location"] = None
        worker._state["country"] = None
