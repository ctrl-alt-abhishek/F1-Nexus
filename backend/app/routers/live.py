"""
app/routers/live.py - /live/* WebSocket and status endpoints.

Spec §5.13:
  GET       /live/status  - Current session status (active, session_type, current_lap)
  WebSocket /live/ws      - Streaming position updates during race weekends

WebSocket protocol:
  - Client connects → receives 'connected' ack message
  - During active sessions: JSON messages pushed every ~2s (from live_timing worker)
  - During off-weekends: connection stays open but no messages (no timeout)
  - On disconnect: client queue automatically cleaned up

Reconnect logic is handled on the frontend (lib/websocket.ts).
The backend accepts the connection regardless — no auth required on WebSocket
(Firebase token in URL param is optional and validated if provided).
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.models.schemas import LiveStatusSchema

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/live", tags=["live"])

# Max messages queued per client before discarding (prevents memory buildup)
_CLIENT_QUEUE_MAXSIZE = 50


# ── GET /live/status ──────────────────────────────────────────────────────────

@router.get("/status", response_model=LiveStatusSchema)
async def get_live_status():
    """
    Current live session status.

    Returns active=False during off-weekends — always safe to call.
    Used by the frontend to show/hide the live race tower.
    """
    from app.services.live_timing import live_worker
    state = await live_worker.get_current_state()
    
    next_race_info = None
    if not state.get("active", False):
        next_race_info = live_worker.get_next_race_info()
        
    return LiveStatusSchema(
        active=state.get("active", False),
        session_type=state.get("session_type"),
        current_lap=state.get("current_lap", 0),
        race_name=state.get("race_name"),
        location=state.get("location"),
        country=state.get("country"),
        next_race=next_race_info,
    )


# ── WebSocket /live/ws ────────────────────────────────────────────────────────

@router.websocket("/ws")
async def live_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for live race position updates.

    Message format (see spec §5.10):
    {
      "type": "position_update",
      "timestamp": "ISO8601",
      "session_type": "Race",
      "lap": 32,
      "drivers": [
        {
          "code": "VER", "position": 1, "gap_to_leader": 0.0,
          "compound": "MEDIUM", "tyre_life": 18,
          "predicted_stint_end": 12,
          "last_lap_s": 90.234,
          "sector1_s": 29.1, "sector2_s": 32.4, "sector3_s": 28.7,
          "drs": true, "pitting": false
        }, ...
      ]
    }

    Special messages:
      {"type": "connected", "active": bool}    - sent on connect
      {"type": "ping"}                          - sent every 30s to keep alive
    """
    from app.services.live_timing import live_worker

    await websocket.accept()
    logger.info("WebSocket client connected from %s", websocket.client)

    # Create a per-client queue
    queue: asyncio.Queue = asyncio.Queue(maxsize=_CLIENT_QUEUE_MAXSIZE)
    live_worker.register_client(queue)

    # Send initial status ack
    state = await live_worker.get_current_state()
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "active": state.get("active", False),
            "session_type": state.get("session_type"),
            "current_lap": state.get("current_lap", 0),
            "race_name": state.get("race_name"),
            "location": state.get("location"),
            "country": state.get("country"),
        }))
    except Exception:
        live_worker.unregister_client(queue)
        return

    # Start keepalive task
    keepalive_task = asyncio.create_task(
        _send_keepalives(websocket),
        name=f"ws_keepalive_{id(websocket)}",
    )

    try:
        while True:
            # Wait for a message from the live timing worker (with timeout for keepalive)
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # No message in 30s — keepalive task handles this
                continue

            try:
                await websocket.send_text(json.dumps(message, default=str))
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WebSocket send failed: %s", exc)
                break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("WebSocket handler error")
    finally:
        keepalive_task.cancel()
        live_worker.unregister_client(queue)
        try:
            await websocket.close()
        except Exception:
            pass


async def _send_keepalives(websocket: WebSocket) -> None:
    """Send a ping message every 25 seconds to keep the WebSocket alive."""
    try:
        while True:
            await asyncio.sleep(25)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass
