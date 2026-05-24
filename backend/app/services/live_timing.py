"""
app/services/live_timing.py - Background live timing worker with in-memory state.

Architecture (spec §5.10):
  - State stored in self._state (plain dict, no Redis)
  - asyncio.Lock protects concurrent reads/writes
  - One asyncio.Queue per connected WebSocket client
  - FastF1 SignalR client runs in a background thread (it's sync internally)
  - Exponential backoff on connection failure (up to 60s)

Notification triggers (from spec §7.2):
  - Pit stop:     TyreLife resets to ≤ 2 → notify followed users
  - Safety car:   TrackStatus → '4' or '5' → notify all safety_car users
  - Fastest lap:  New fastest lap → notify followed users
  - Race start:   First lap data received → notify all race_start users

Off-weekend behaviour:
  - _state['active'] = False (always)
  - GET /live/status returns active=False gracefully
  - WebSocket connections are accepted but receive no messages until active=True
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def check_token_valid() -> bool:
    import os
    import fastf1.livetiming.client as client
    try:
        g = client.get_auth_token.__globals__
        _verify_jwt = g['_verify_jwt']
        JWKS_URL = g['JWKS_URL']
        AUTH_DATA_FILE = g['AUTH_DATA_FILE']
        if os.path.exists(AUTH_DATA_FILE):
            with open(AUTH_DATA_FILE) as f:
                token = f.read().strip()
            if token:
                _verify_jwt(token, JWKS_URL)
                return True
    except Exception as e:
        logger.warning("FastF1 token verification failed: %s", e)
    return False


from fastf1.livetiming.client import SignalRClient

class MemorySignalRClient(SignalRClient):
    """
    Custom SignalRClient that overrides output file writing to process messages
    directly in memory via a callback.
    """
    def __init__(self, callback, no_auth: bool = False, logger=None):
        # Pass dummy filename to satisfy super().__init__
        # Use timeout=15 to fall back to simulation quickly if F1 feed is idle
        super().__init__(filename="dummy.txt", no_auth=no_auth, logger=logger, timeout=15)
        self.callback = callback

    def _run(self):
        # Override to avoid opening files
        import requests
        from signalrcore.hub_connection_builder import HubConnectionBuilder
        from fastf1.livetiming.client import get_auth_token

        # Pre-negotiate to the get a valid AWSALBCORS header token
        r = requests.options(self._negotiate_url, headers=self.headers)
        if 'AWSALBCORS' in r.cookies:
            self.headers.update(
                {"Cookie": f"AWSALBCORS={r.cookies['AWSALBCORS']}"}
            )

        # Configure and create connection
        options = {
            "verify_ssl": True,
            "headers": self.headers
        }
        if not self._no_auth:
            options["access_token_factory"] = get_auth_token

        self._connection = HubConnectionBuilder() \
            .with_url(self._connection_url, options=options) \
            .configure_logging(logging.INFO) \
            .build()

        self._connection.on_open(self._on_connect)
        self._connection.on_close(self._on_close)
        self._connection.on('feed', self._on_message)

        self._connection.start()

        # wait for connection to be established
        while not self._is_connected:
            time.sleep(0.1)

        self._connection.send(
            "Subscribe", [self.topics], on_invocation=self._on_message
        )

    def _on_message(self, msg):
        self._t_last_message = time.time()
        if isinstance(msg, list) and len(msg) >= 3:
            try:
                self.callback(msg[0], msg[1], msg[2])
            except Exception:
                self.logger.exception("Callback error during message processing")

    def _exit(self):
        if self._connection:
            self._connection.stop()


class LiveTimingWorker:
    """
    Singleton background worker that tracks live FastF1 timing during race weekends.

    Usage:
        from app.services.live_timing import live_worker
        await live_worker.start()   # called in app lifespan
        await live_worker.stop()    # called on shutdown

    WebSocket endpoints register/unregister client queues via:
        live_worker.register_client(queue)
        live_worker.unregister_client(queue)
    """

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
        }
        self._lock = asyncio.Lock()
        # Each connected WebSocket client gets an asyncio.Queue entry here.
        # Using a set of queues so broadcast is O(n) over active connections.
        self._clients: set[asyncio.Queue] = set()
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        # Track previous tyre life to detect pit stops
        self._prev_tyre_life: dict[str, int] = {}
        # Track fastest lap for notification deduplication
        self._fastest_lap_s: float = float("inf")
        # Real live timing mappings
        self._driver_map: dict[str, int] = {}
        self._round_id: int | None = None
        self._total_laps: int = 70

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start the background monitor task.
        Checks periodically if a live session is active and connects if so.
        """
        self._running = True
        self._monitor_task = asyncio.create_task(
            self._session_monitor(), name="live_timing_monitor"
        )
        logger.info("Live timing worker started")

    async def stop(self) -> None:
        """Gracefully stop the worker on app shutdown."""
        self._running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Live timing worker stopped")

    # ── Client management ─────────────────────────────────────────────────────

    def register_client(self, queue: asyncio.Queue) -> None:
        """Register a new WebSocket client. Called when client connects."""
        self._clients.add(queue)
        logger.debug("WebSocket client registered (%d total)", len(self._clients))

    def unregister_client(self, queue: asyncio.Queue) -> None:
        """Unregister a WebSocket client. Called when client disconnects."""
        self._clients.discard(queue)
        logger.debug("WebSocket client unregistered (%d total)", len(self._clients))

    # ── State access ──────────────────────────────────────────────────────────

    async def get_current_state(self) -> dict:
        """
        Return a copy of the current live state.
        Never returns the live dict directly — callers must not mutate it.
        Always safe to call even during off-weekends (returns active=False).
        """
        async with self._lock:
            return dict(self._state)

    def get_next_race_info(self) -> dict | None:
        """
        Get the name, location, date, and timing of the next upcoming race.
        """
        try:
            import fastf1
            import pandas as pd
            from datetime import datetime, timezone
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
        except Exception:
            logger.exception("Failed to get next race info")
        return None

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(self, data: dict) -> None:
        """
        Push a message to all connected WebSocket clients.
        Dead queues (disconnected clients) are silently skipped.
        """
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

    # ── Session monitor ───────────────────────────────────────────────────────

    async def _session_monitor(self) -> None:
        """
        Background task that polls for an active F1 session every 60 seconds.
        When an active session is detected, connects the live timing client.
        Reconnects with exponential backoff on failure.
        """
        backoff = 5.0
        max_backoff = 60.0

        while self._running:
            try:
                is_active = await asyncio.to_thread(self._check_session_active)
                if is_active:
                    logger.info("Live session detected — connecting timing client")
                    received_any = await self._run_live_client()
                    if received_any:
                        backoff = 5.0  # Reset on clean exit with data
                    else:
                        logger.info("No live timing data received (feed silent). Waiting 60s before retrying.")
                        backoff = 60.0
                else:
                    # No session active — quietly wait
                    async with self._lock:
                        self._state["active"] = False
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Session monitor error — retrying in %.0fs", backoff)
                backoff = min(backoff * 2, max_backoff)

            await asyncio.sleep(backoff)

    def _check_session_active(self) -> bool:
        """
        Check whether a live F1 timing session is currently running.

        FastF1 doesn't expose a simple 'is_live()' check, so we use a heuristic:
        attempt to load the event schedule for the current year and see if today
        falls within a race weekend window (Friday–Sunday).
        Returns False during off-weekends rather than raising.
        """
        from app.config import settings
        
        if getattr(settings, "SIMULATE_LIVE_TIMING", False):
            logger.info("SIMULATE_LIVE_TIMING is enabled. Forcing live session active.")
            try:
                import fastf1
                from datetime import date
                today = date.today()
                schedule = fastf1.get_event_schedule(today.year, include_testing=False)
                for _, event in schedule.iterrows():
                    event_date = event.get("EventDate")
                    if event_date is not None:
                        if hasattr(event_date, "date"):
                            event_date = event_date.date()
                        delta = (event_date - today).days
                        if -1 <= delta <= 3:
                            self._active_event_name = event.get("EventName", "Canada")
                            logger.info("Active weekend: %s", self._active_event_name)
                            return True
            except Exception as e:
                logger.debug("Failed schedule check in simulation mode: %s", e)
            self._active_event_name = "Canada"
            return True

        try:
            import fastf1
            from datetime import date

            today = date.today()
            schedule = fastf1.get_event_schedule(today.year, include_testing=False)

            for _, event in schedule.iterrows():
                event_date = event.get("EventDate")
                if event_date is None:
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
                    self._active_event_name = event.get("EventName", "")
                    return True

        except Exception as exc:
            logger.debug("Session check failed (normal off-weekend): %s", exc)

        return False

    async def _run_live_client(self) -> None:
        """
        Connect to FastF1 live timing and process updates until session ends.
        Runs the synchronous SignalR client in a background thread.
        """
        import fastf1
        from app.config import settings

        # Check if we should force simulation mode
        if getattr(settings, "SIMULATE_LIVE_TIMING", False):
            logger.info("SIMULATE_LIVE_TIMING is enabled. Running simulation.")
            await self._run_simulation_client()
            return True

        # Check if the livetiming client module is available
        try:
            import fastf1.livetiming.client
        except ImportError:
            logger.warning("FastF1 livetiming.client module not found. Running simulation.")
            await self._run_simulation_client()
            return True

        # Verify token validity to prevent blocking if expired/invalid
        token_valid = check_token_valid()
        no_auth = not token_valid

        if no_auth:
            logger.info("No valid FastF1 subscription token found. Connecting in no_auth=True mode.")
        else:
            logger.info("Valid FastF1 subscription token found. Connecting in authenticated mode.")

        # Initialize round and driver list dynamically from database
        from app.database import get_db_context
        from sqlalchemy import text
        try:
            with get_db_context() as db:
                active_name = getattr(self, "_active_event_name", None) or "Canada"
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
                    
                driver_rows = db.execute(text("SELECT DISTINCT driver_code FROM laps")).fetchall()
                driver_codes = sorted([r[0] for r in driver_rows])
                self._driver_map = {code: idx for idx, code in enumerate(driver_codes)}
        except Exception:
            logger.exception("Failed to initialize round info for live timing predictions")

        loop = asyncio.get_event_loop()

        active_name = getattr(self, "_active_event_name", None) or "Canada"
        race_name, location, country = active_name, "", ""
        try:
            import fastf1
            schedule = fastf1.get_event_schedule(datetime.now().year, include_testing=False)
            for _, event in schedule.iterrows():
                if event.get("EventName") == active_name:
                    race_name = event.get("EventName")
                    location = event.get("Location")
                    country = event.get("Country")
                    break
        except Exception as e:
            logger.debug("Failed to populate active event details: %s", e)

        async with self._lock:
            # Do not set active=True here yet. We are connecting.
            # Once we receive the first message, _handle_message will set active=True.
            self._state["active"] = False
            self._state["session_type"] = "Race"
            self._state["race_name"] = race_name
            self._state["location"] = location
            self._state["country"] = country

        received_messages = False
        def _on_message(msg_type: str, msg_data, timestamp: str):
            """Called by the FastF1 SignalR client on each timing message."""
            nonlocal received_messages
            received_messages = True
            asyncio.run_coroutine_threadsafe(
                self._handle_message(msg_type, msg_data, timestamp),
                loop,
            )

        # Run the blocking SignalR client in a thread
        try:
            client = MemorySignalRClient(
                callback=_on_message,
                no_auth=no_auth,
                logger=logger,
            )
            # Register our callback for position/car data messages
            await asyncio.to_thread(self._run_client_blocking, client)
            if getattr(settings, "SIMULATE_LIVE_TIMING", False):
                logger.info("Real live client finished. Falling back to simulation.")
                await self._run_simulation_client()
                return True
            else:
                logger.info("Real live client finished. SIMULATE_LIVE_TIMING is False, skipping simulation fallback.")
                return received_messages
        except Exception:
            logger.exception("Live timing client disconnected with error")
            if getattr(settings, "SIMULATE_LIVE_TIMING", False):
                logger.info("Falling back to simulation.")
                await self._run_simulation_client()
                return True
            return False
        finally:
            async with self._lock:
                self._state["active"] = False
                self._state["drivers"] = {}
                self._state["race_name"] = None
                self._state["location"] = None
                self._state["country"] = None

    def _run_client_blocking(self, client) -> None:
        """Blocking runner for the SignalR client (executed in thread pool)."""
        try:
            client.start()
        except Exception as exc:
            logger.debug("SignalR client exited: %s", exc)

    async def _run_simulation_client(self) -> None:
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
                active_name = getattr(self, "_active_event_name", None) or "Canada"
                
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
            await self._run_synthetic_mock()
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
            await self._run_synthetic_mock()
            return
            
        if not laps_rows:
            logger.warning("No laps found for round %d. Running purely synthetic mock.", rnd_id)
            await self._run_synthetic_mock()
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
        
        active_name = getattr(self, "_active_event_name", None) or rnd_name or "Canada"
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

        async with self._lock:
            self._state["active"] = True
            self._state["session_type"] = "Race"
            self._state["current_lap"] = 0
            self._state["drivers"] = {}
            self._state["race_name"] = race_name
            self._state["location"] = location
            self._state["country"] = country
            self._prev_tyre_life = {}
            self._fastest_lap_s = float("inf")
            
        cumulative_times = {}
        
        for lap_num in range(1, max_laps + 1):
            if not self._running:
                break
                
            async with self._lock:
                if not self._state["active"]:
                    break
            
            lap_data = laps_by_num[lap_num]
            if not lap_data:
                await asyncio.sleep(2)
                continue
                
            logger.info("Simulating Lap %d/%d...", lap_num, max_laps)
            
            if lap_num == 1:
                asyncio.create_task(self._notify_race_start())
                
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
                asyncio.create_task(self._notify_safety_car(lap_num))

            from app.ml.loader import models
            from app.ml.strategy.predict import recommend_pit_window
            
            async with self._lock:
                self._state["current_lap"] = lap_num
                
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
                        asyncio.create_task(self._notify_pit_stop(code, next_rec["compound"] or "MEDIUM"))
                        
                    if lap_time_s and 0 < lap_time_s < self._fastest_lap_s:
                        self._fastest_lap_s = lap_time_s
                        asyncio.create_task(self._notify_fastest_lap(code, lap_time_s))
                        
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
                            
                    self._state["drivers"][code] = {
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
            await self._broadcast_state(timestamp)
            await asyncio.sleep(2.0)
            
        async with self._lock:
            self._state["active"] = False
            self._state["drivers"] = {}
            self._state["race_name"] = None
            self._state["location"] = None
            self._state["country"] = None
        logger.info("Simulation finished.")

    async def _run_synthetic_mock(self) -> None:
        """Purely synthetic simulation when no rounds are in DB."""
        logger.info("Running synthetic live timing mock...")
        drivers_list = ["VER", "HAM", "NOR", "LEC", "SAI", "PIA", "RUS", "PER", "ALO", "STR"]
        
        async with self._lock:
            self._state["active"] = True
            self._state["session_type"] = "Race"
            self._state["current_lap"] = 0
            self._state["drivers"] = {}
            self._state["race_name"] = "Mock Grand Prix"
            self._state["location"] = "Mock Location"
            self._state["country"] = "Mock Country"
            
        import random
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
            if not self._running:
                break
                
            async with self._lock:
                if not self._state["active"]:
                    break
                    
                self._state["current_lap"] = lap_num
                
                if lap_num == 1:
                    asyncio.create_task(self._notify_race_start())
                    
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
                        asyncio.create_task(self._notify_pit_stop(code, ds["compound"]))
                        
                    ds["pitting"] = pitting
                    
                if random.random() < 0.15:
                    swap_idx = random.randint(1, len(drivers_list) - 1)
                    drivers_list[swap_idx], drivers_list[swap_idx - 1] = drivers_list[swap_idx - 1], drivers_list[swap_idx]
                    
                for idx, code in enumerate(drivers_list):
                    ds = driver_states[code]
                    ds["position"] = idx + 1
                    ds["gap_to_leader"] = idx * 1.2 + random.uniform(-0.2, 0.2)
                    ds["drs"] = idx > 0 and (ds["gap_to_leader"] - driver_states[drivers_list[idx - 1]]["gap_to_leader"] < 1.0)
                    
                    self._state["drivers"][code] = dict(ds)
                    
            timestamp = datetime.now(timezone.utc).isoformat()
            await self._broadcast_state(timestamp)
            await asyncio.sleep(2.0)
            
        async with self._lock:
            self._state["active"] = False
            self._state["drivers"] = {}
            self._state["race_name"] = None
            self._state["location"] = None
            self._state["country"] = None

    async def _handle_message(self, msg_type: str, msg_data, timestamp: str) -> None:
        """
        Process an incoming live timing message and update state.

        FastF1 delivers messages with these relevant types:
          TimingData        - lap times, sectors, gaps
          CarData           - throttle, brake, DRS
          Position          - GPS coordinates (unused here)
          SessionStatus     - session state changes
          TrackStatus       - safety car, VSC flags
          TimingAppData     - tyre data (compound + age)
        """
        async with self._lock:
            state = self._state
            if not state.get("active", False):
                state["active"] = True
                logger.info("Live timing telemetry received — setting active=True")

            if msg_type == "SessionStatus":
                status = msg_data.get("Status", "")
                if status == "Finished":
                    state["active"] = False
                    logger.info("Session finished")

            elif msg_type == "TrackStatus":
                status_code = str(msg_data.get("Status", "1"))
                if status_code in ("4", "5"):
                    logger.info("Safety car/VSC deployed: status=%s", status_code)
                    asyncio.create_task(self._notify_safety_car(state.get("current_lap", 0)))

            elif msg_type == "TimingData":
                # Parse per-driver timing info
                lines = msg_data.get("Lines", {})
                for driver_code, timing in lines.items():
                    if driver_code not in state["drivers"]:
                        state["drivers"][driver_code] = {
                            "code": driver_code,
                            "position": 0,
                            "gap_to_leader": 0.0,
                            "compound": None,
                            "tyre_life": 0,
                            "predicted_stint_end": None,
                            "last_lap_s": None,
                            "sector1_s": None,
                            "sector2_s": None,
                            "sector3_s": None,
                            "drs": False,
                            "pitting": False,
                        }
                    drv = state["drivers"][driver_code]

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
                        # Fastest lap tracking
                        lap_s = drv["last_lap_s"] or 0.0
                        if 0 < lap_s < self._fastest_lap_s:
                            self._fastest_lap_s = lap_s
                            asyncio.create_task(
                                self._notify_fastest_lap(driver_code, lap_s)
                            )

                    # Sector times
                    sectors = timing.get("Sectors", {})
                    if "0" in sectors:
                        drv["sector1_s"] = _safe_float(sectors["0"].get("Value"))
                    if "1" in sectors:
                        drv["sector2_s"] = _safe_float(sectors["1"].get("Value"))
                    if "2" in sectors:
                        drv["sector3_s"] = _safe_float(sectors["2"].get("Value"))

                    # Lap number
                    if "NumberOfLaps" in timing:
                        lap_num = _safe_int(timing["NumberOfLaps"])
                        if lap_num and lap_num > state.get("current_lap", 0):
                            state["current_lap"] = lap_num
                            # Race start notification on first lap
                            if lap_num == 1:
                                asyncio.create_task(self._notify_race_start())

            elif msg_type == "TimingAppData":
                # Tyre compound + age data
                lines = msg_data.get("Lines", {})
                for driver_code, app_data in lines.items():
                    stints = app_data.get("Stints", {})
                    if not stints:
                        continue
                    # Latest stint is the highest-keyed entry
                    latest_stint = stints[max(stints.keys())]
                    compound = latest_stint.get("Compound", "UNKNOWN")
                    tyre_life = _safe_int(latest_stint.get("TotalLaps", 0))

                    if driver_code in state["drivers"]:
                        prev_life = self._prev_tyre_life.get(driver_code, 0)
                        state["drivers"][driver_code]["compound"] = compound
                        state["drivers"][driver_code]["tyre_life"] = tyre_life

                        # Pit stop detection: tyre life resets to ≤ 2
                        if tyre_life is not None and tyre_life <= 2 and prev_life > 2:
                            asyncio.create_task(
                                self._notify_pit_stop(driver_code, compound)
                            )

                        if tyre_life is not None:
                            self._prev_tyre_life[driver_code] = tyre_life

            # Run ML predictions for all active drivers before broadcasting
            from app.ml.loader import models
            if models.strategy is not None and models.degradation is not None:
                from app.ml.strategy.predict import recommend_pit_window
                for code, drv in state["drivers"].items():
                    try:
                        driver_enc = getattr(self, "_driver_map", {}).get(code, 0)
                        pred_res = recommend_pit_window(
                            models.strategy,
                            models.degradation,
                            current_lap=state.get("current_lap", 1) or 1,
                            tire_age=drv.get("tyre_life", 1) or 1,
                            compound=drv.get("compound", "MEDIUM") or "MEDIUM",
                            position=drv.get("position", 10) or 10,
                            gap_ahead=0.0,  # default
                            total_laps=getattr(self, "_total_laps", 70) or 70,
                            driver_enc=driver_enc,
                            stint=1,  # default
                        )
                        drv["predicted_stint_end"] = pred_res["recommended_lap"]
                    except Exception as e:
                        logger.debug("Failed to calculate live prediction for %s: %s", code, e)

        # Broadcast current state to WebSocket clients
        await self._broadcast_state(timestamp)

    async def _broadcast_state(self, timestamp: str) -> None:
        """Build a LiveUpdateSchema-shaped dict and broadcast to all clients."""
        async with self._lock:
            state = self._state

        if not state.get("active"):
            return

        drivers_list = list(state.get("drivers", {}).values())
        drivers_list.sort(key=lambda d: d.get("position", 99))

        message = {
            "type": "position_update",
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "session_type": state.get("session_type", "Race"),
            "lap": state.get("current_lap", 0),
            "drivers": drivers_list,
        }
        await self.broadcast(message)

    # ── Notification triggers ─────────────────────────────────────────────────

    async def _notify_pit_stop(self, driver_code: str, compound: str) -> None:
        """Notify users who follow this driver that they've pitted."""
        try:
            await _notify_followed_driver_users(
                driver_code=driver_code,
                title=f"🟢 {driver_code} has pitted!",
                body=f"{driver_code} is now on {compound} tyres.",
                notification_pref="pit_alerts",
            )
        except Exception as exc:
            logger.debug("Pit stop notification failed: %s", exc)

    async def _notify_safety_car(self, lap: int) -> None:
        """Notify all users with safety_car preference enabled."""
        try:
            from app.services.notifications import notify_broadcast
            await notify_broadcast(
                title="🟡 Safety Car",
                body=f"Safety car deployed on lap {lap}.",
                notification_pref="safety_car",
            )
        except Exception as exc:
            logger.debug("Safety car notification failed: %s", exc)

    async def _notify_fastest_lap(self, driver_code: str, lap_s: float) -> None:
        """Notify users following this driver of a new fastest lap."""
        try:
            mins = int(lap_s // 60)
            secs = lap_s % 60
            formatted = f"{mins}:{secs:06.3f}"
            await _notify_followed_driver_users(
                driver_code=driver_code,
                title=f"⚡ {driver_code} sets fastest lap",
                body=f"{driver_code} — {formatted}",
                notification_pref="fastest_lap",
            )
        except Exception as exc:
            logger.debug("Fastest lap notification failed: %s", exc)

    async def _notify_race_start(self) -> None:
        """Notify all users with race_start preference."""
        try:
            from app.services.notifications import notify_broadcast
            await notify_broadcast(
                title="🏁 Race Start",
                body="The race is underway!",
                notification_pref="race_start",
            )
        except Exception as exc:
            logger.debug("Race start notification failed: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> float | None:
    try:
        return float(str(value).replace(":", "").replace("+", "") or 0)
    except (TypeError, ValueError):
        return None


async def _notify_followed_driver_users(
    driver_code: str,
    title: str,
    body: str,
    notification_pref: str,
) -> None:
    """
    Find all Firestore users who follow driver_code and have the given
    notification preference enabled, then notify each one.
    """
    try:
        from app.firebase import get_firestore_client
        from app.services.notifications import notify_user

        db_fs = get_firestore_client()
        # Query Firestore for users with this driver in their followed list
        docs = (
            db_fs.collection("users")
            .where("followed_drivers", "array_contains", driver_code)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            prefs = data.get("notification_prefs", {})
            if prefs.get(notification_pref, False):
                await notify_user(doc.id, title, body)
    except Exception as exc:
        logger.debug("_notify_followed_driver_users failed: %s", exc)


# ── Singleton ─────────────────────────────────────────────────────────────────
# Imported by main.py lifespan and live.py router.
live_worker = LiveTimingWorker()
