"""
app/services/live_timing.py - Background live timing worker with in-memory state.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.services.schedule_utils import get_active_event, get_next_race_info, get_event_details
from app.services.signalr_client import MemorySignalRClient, check_token_valid, run_client_blocking
from app.services.simulation import run_simulation_client

logger = logging.getLogger(__name__)

def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _safe_float(value) -> float | None:
    try:
        val_str = str(value).replace("+", "")
        if ":" in val_str:
            parts = val_str.split(":")
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        return float(val_str or 0)
    except (TypeError, ValueError):
        return None

class LiveTimingWorker:
    def __init__(self):
        self._state: dict = {
            "active": False,
            "session_type": None,
            "current_lap": 0,
            "last_updated": 0.0,
            "drivers": {},
            "race_name": None,
            "location": None,
            "country": None,
            "rc_messages": [],
        }
        self._lock = asyncio.Lock()
        self._clients: set[asyncio.Queue] = set()
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._prev_tyre_life: dict[str, int] = {}
        self._fastest_lap_s: float = float("inf")
        self._driver_map: dict[str, int] = {}
        self._car_to_driver: dict[str, dict] = {}
        self._round_id: int | None = None
        self._total_laps: int = 70
        self._active_event_name: str | None = None

    async def start(self) -> None:
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._session_monitor(), name="live_timing_monitor"
        )
        logger.info("Live timing worker started")

    async def stop(self) -> None:
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Live timing worker stopped")

    def register_client(self, queue: asyncio.Queue) -> None:
        self._clients.add(queue)

    def unregister_client(self, queue: asyncio.Queue) -> None:
        self._clients.discard(queue)

    async def get_current_state(self) -> dict:
        async with self._lock:
            return dict(self._state)

    def get_next_race_info(self) -> dict | None:
        return get_next_race_info()

    async def broadcast(self, data: dict) -> None:
        if not self._clients:
            return

        dead: set[asyncio.Queue] = set()
        for queue in list(self._clients):
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                dead.add(queue)

        for q in dead:
            self._clients.discard(q)

    async def _session_monitor(self) -> None:
        backoff = 5.0
        max_backoff = 60.0

        while self._running:
            try:
                is_active = await asyncio.to_thread(self._check_session_active)
                if is_active:
                    logger.info("Live session detected — connecting timing client")
                    received_any = await self._run_live_client()
                    if received_any:
                        backoff = 5.0
                    else:
                        logger.info("No live timing data received (feed silent). Waiting 10s before retrying.")
                        backoff = 10.0
                else:
                    async with self._lock:
                        self._state["active"] = False
                    backoff = 60.0
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Session monitor error — retrying in %.0fs", backoff)
                backoff = min(backoff * 2, max_backoff)

            await asyncio.sleep(backoff)

    def _check_session_active(self) -> bool:
        if getattr(settings, "SIMULATE_LIVE_TIMING", False):
            self._active_event_name = get_active_event() or "Simulated Grand Prix"
            return True
        
        active_event = get_active_event()
        if active_event:
            self._active_event_name = active_event
            return True
            
        return False

    async def _run_live_client(self) -> bool:
        if getattr(settings, "SIMULATE_LIVE_TIMING", False):
            await run_simulation_client(self)
            return True

        token_valid = await asyncio.to_thread(check_token_valid)
        no_auth = not token_valid

        from app.database import get_db_context
        from sqlalchemy import text
        try:
            with get_db_context() as db:
                active_name = self._active_event_name or "Unknown"
                row = db.execute(
                    text("SELECT id, name FROM rounds WHERE name ILIKE :name LIMIT 1"),
                    {"name": f"%{active_name}%"}
                ).fetchone()
                if row:
                    self._round_id = row[0]
                    max_laps = db.execute(
                        text("SELECT MAX(lap_number) FROM laps WHERE round_id = :round_id"),
                        {"round_id": self._round_id}
                    ).scalar()
                    self._total_laps = max_laps or 70
                    
                team_colors = {
                    "Red Bull Racing": "#3671C6", "Ferrari": "#E8002D", "Mercedes": "#27F4D2",
                    "McLaren": "#FF8000", "Aston Martin": "#229971", "Alpine": "#0093CC",
                    "Williams": "#37BEDD", "RB": "#6692FF", "Kick Sauber": "#52E252", "Haas": "#B6BABD"
                }
                
                driver_rows = db.execute(text("""
                    SELECT ds.car_number, d.code, d.full_name, c.name as team_name
                    FROM driver_season ds
                    JOIN drivers d ON ds.driver_code = d.code
                    JOIN constructors c ON ds.constructor_id = c.id
                    WHERE ds.season_year = :year
                """), {"year": datetime.now(timezone.utc).year}).fetchall()
                
                self._car_to_driver = {}
                for r in driver_rows:
                    car_no, code, name, team = str(r[0]), r[1], r[2], r[3]
                    self._car_to_driver[car_no] = {
                        "code": code, "name": name, "team": team,
                        "color": team_colors.get(team, "#FFFFFF")
                    }
                
                self._driver_map = {r[1]: idx for idx, r in enumerate(driver_rows)}
                
                async with self._lock:
                    if "drivers" not in self._state:
                        self._state["drivers"] = {}
                    for car_no, info in self._car_to_driver.items():
                        if car_no not in self._state["drivers"]:
                            self._state["drivers"][car_no] = {
                                "code": info["code"],
                                "name": info["name"],
                                "color": info["color"],
                                "position": 99, "gap_to_leader": 0.0,
                                "compound": None, "tyre_life": 0, "predicted_stint_end": None,
                                "last_lap_s": None, "sector1_s": None, "sector2_s": None, "sector3_s": None,
                                "drs": False, "pitting": False,
                            }
        except Exception:
            logger.exception("Failed to initialize round info for live timing predictions")

        loop = asyncio.get_running_loop()
        race_name, location, country = await asyncio.to_thread(
            get_event_details, self._active_event_name or "Unknown"
        )

        async with self._lock:
            self._state["active"] = False
            self._state["session_type"] = "Session"
            self._state["race_name"] = race_name
            self._state["location"] = location
            self._state["country"] = country

        received_messages = False
        def _on_message(msg_type: str, msg_data, timestamp: str):
            nonlocal received_messages
            received_messages = True
            asyncio.run_coroutine_threadsafe(
                self._handle_message(msg_type, msg_data, timestamp),
                loop,
            )

        try:
            client = MemorySignalRClient(
                callback=_on_message,
                no_auth=no_auth,
                logger=logger,
                timeout=60,
            )
            await asyncio.to_thread(run_client_blocking, client)
            if getattr(settings, "SIMULATE_LIVE_TIMING", False):
                await run_simulation_client(self)
                return True
            return received_messages
        except Exception:
            logger.exception("Live timing client disconnected with error")
            if getattr(settings, "SIMULATE_LIVE_TIMING", False):
                await run_simulation_client(self)
                return True
            return False
        finally:
            async with self._lock:
                self._state["active"] = False

    async def _handle_message(self, msg_type: str, msg_data, timestamp: str) -> None:
        async with self._lock:
            state = self._state
            if not state.get("active", False):
                state["active"] = True

            if msg_type == "SessionStatus":
                if msg_data.get("Status", "") == "Finished":
                    state["active"] = False

            elif msg_type == "TrackStatus":
                status_code = str(msg_data.get("Status", "1"))
                if status_code in ("4", "5"):
                    asyncio.create_task(self._notify_safety_car(state.get("current_lap", 0)))

            elif msg_type == "SessionInfo":
                if "Name" in msg_data:
                    state["session_type"] = msg_data["Name"]
                    
            elif msg_type == "RaceControlMessages":
                messages = msg_data.get("Messages", [])
                if "rc_messages" not in state:
                    state["rc_messages"] = []
                for m in messages:
                    state["rc_messages"].append({
                        "category": m.get("Category", "FLAG"),
                        "message": m.get("Message", "")
                    })
                state["rc_messages"] = state["rc_messages"][-10:]

            elif msg_type == "TimingData":
                lines = msg_data.get("Lines", {})
                for car_number, timing in lines.items():
                    car_str = str(car_number)
                    if car_str not in state["drivers"]:
                        d_info = self._car_to_driver.get(car_str, {"code": car_str, "name": f"Driver {car_str}", "color": "#FFFFFF"})
                        state["drivers"][car_str] = {
                            "code": d_info["code"],
                            "name": d_info["name"],
                            "color": d_info["color"],
                            "position": 0, "gap_to_leader": 0.0,
                            "compound": None, "tyre_life": 0, "predicted_stint_end": None,
                            "last_lap_s": None, "sector1_s": None, "sector2_s": None, "sector3_s": None,
                            "drs": False, "pitting": False,
                        }
                    drv = state["drivers"][car_str]

                    if "Position" in timing:
                        drv["position"] = _safe_int(timing["Position"])
                    if "GapToLeader" in timing:
                        drv["gap_to_leader"] = _safe_float(timing["GapToLeader"])
                    if "LastLapTime" in timing:
                        lt = timing["LastLapTime"]
                        if isinstance(lt, dict):
                            drv["last_lap_s"] = _safe_float(lt.get("Value", 0))
                        else:
                            drv["last_lap_s"] = _safe_float(lt)
                            
                        lap_s = drv["last_lap_s"] or 0.0
                        if 0 < lap_s < self._fastest_lap_s:
                            self._fastest_lap_s = lap_s
                            asyncio.create_task(self._notify_fastest_lap(drv["code"], lap_s))

                    sectors = timing.get("Sectors", {})
                    if "0" in sectors: drv["sector1_s"] = _safe_float(sectors["0"].get("Value"))
                    if "1" in sectors: drv["sector2_s"] = _safe_float(sectors["1"].get("Value"))
                    if "2" in sectors: drv["sector3_s"] = _safe_float(sectors["2"].get("Value"))

                    if "NumberOfLaps" in timing:
                        lap_num = _safe_int(timing["NumberOfLaps"])
                        if lap_num and lap_num > state.get("current_lap", 0):
                            state["current_lap"] = lap_num
                            if lap_num == 1:
                                asyncio.create_task(self._notify_race_start())

            elif msg_type == "TimingAppData":
                lines = msg_data.get("Lines", {})
                for car_number, app_data in lines.items():
                    stints = app_data.get("Stints", {})
                    if not stints: continue
                    latest_stint = stints[max(stints.keys())]
                    compound = latest_stint.get("Compound", "UNKNOWN")
                    tyre_life = _safe_int(latest_stint.get("TotalLaps", 0))

                    car_str = str(car_number)
                    if car_str in state["drivers"]:
                        prev_life = self._prev_tyre_life.get(car_str, 0)
                        state["drivers"][car_str]["compound"] = compound
                        state["drivers"][car_str]["tyre_life"] = tyre_life

                        if tyre_life is not None and tyre_life <= 2 and prev_life > 2:
                            asyncio.create_task(self._notify_pit_stop(state["drivers"][car_str]["code"], compound))
                        if tyre_life is not None:
                            self._prev_tyre_life[car_str] = tyre_life

            from app.ml.loader import models
            if models.strategy is not None and models.degradation is not None:
                from app.ml.strategy.predict import recommend_pit_window
                for car_str, drv in state["drivers"].items():
                    try:
                        driver_enc = self._driver_map.get(drv.get("code", ""), 0)
                        pred_res = recommend_pit_window(
                            models.strategy, models.degradation,
                            current_lap=state.get("current_lap", 1) or 1,
                            tire_age=drv.get("tyre_life", 1) or 1,
                            compound=drv.get("compound", "MEDIUM") or "MEDIUM",
                            position=drv.get("position", 10) or 10,
                            gap_ahead=0.0, total_laps=self._total_laps or 70,
                            driver_enc=driver_enc, stint=1,
                        )
                        drv["predicted_stint_end"] = pred_res["recommended_lap"]
                    except Exception:
                        pass

        await self._broadcast_state(timestamp)

    async def _broadcast_state(self, timestamp: str) -> None:
        async with self._lock:
            state = self._state

        if not state.get("active"):
            return

        drivers_list = list(state.get("drivers", {}).values())
        drivers_list.sort(key=lambda d: d.get("position", 99))

        message = {
            "type": "position_update",
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "session_type": state.get("session_type", "Session"),
            "lap": state.get("current_lap", 0),
            "drivers": drivers_list,
            "rc_messages": state.get("rc_messages", [])
        }
        await self.broadcast(message)

    async def _notify_pit_stop(self, driver_code: str, compound: str) -> None:
        try:
            await _notify_followed_driver_users(
                driver_code=driver_code,
                title=f"🟢 {driver_code} has pitted!",
                body=f"{driver_code} is now on {compound} tyres.",
                notification_pref="pit_alerts",
            )
        except Exception:
            pass

    async def _notify_safety_car(self, lap: int) -> None:
        # Added deduplication to prevent multiple notifications for the same safety car
        if getattr(self, "_last_sc_lap", -1) == lap:
            return
        self._last_sc_lap = lap
        try:
            from app.services.notifications import notify_broadcast
            await notify_broadcast(
                title="🟡 Safety Car", body=f"Safety car deployed on lap {lap}.", notification_pref="safety_car"
            )
        except Exception:
            pass

    async def _notify_fastest_lap(self, driver_code: str, lap_s: float) -> None:
        try:
            mins = int(lap_s // 60)
            secs = lap_s % 60
            await _notify_followed_driver_users(
                driver_code=driver_code,
                title=f"⚡ {driver_code} sets fastest lap",
                body=f"{driver_code} — {mins}:{secs:06.3f}",
                notification_pref="fastest_lap",
            )
        except Exception:
            pass

    async def _notify_race_start(self) -> None:
        try:
            from app.services.notifications import notify_broadcast
            await notify_broadcast(
                title="🏁 Race Start", body="The race is underway!", notification_pref="race_start"
            )
        except Exception:
            pass

async def _notify_followed_driver_users(driver_code: str, title: str, body: str, notification_pref: str) -> None:
    try:
        from app.firebase import get_firestore_client
        from app.services.notifications import notify_user
        db_fs = get_firestore_client()
        docs = db_fs.collection("users").where("followed_drivers", "array_contains", driver_code).stream()
        for doc in docs:
            data = doc.to_dict()
            if data.get("notification_prefs", {}).get(notification_pref, False):
                await notify_user(doc.id, title, body)
    except Exception:
        pass

live_worker = LiveTimingWorker()
