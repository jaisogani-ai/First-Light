"""Digital Twin REST + background streaming loop that persists real ticks and broadcasts them."""

import asyncio
import json

from fastapi import APIRouter
from sqlalchemy import desc, select

from backend.db import engine
from backend.digital_twin import DigitalTwinState
from backend.models import telemetry
from backend.ws_manager import ws_manager

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

_twin = DigitalTwinState()
_task: asyncio.Task | None = None
TICK_SECONDS = 1.0


async def _loop():
    while True:
        tick = _twin.step(dt=TICK_SECONDS)
        with engine.begin() as conn:
            conn.execute(telemetry.insert().values(
                spacecraft_id=None,
                omega_x=tick["omega_x"], omega_y=tick["omega_y"], omega_z=tick["omega_z"],
                reaction_wheel_momentum=tick["reaction_wheel_momentum"],
                battery_soc_pct=tick["battery_soc_pct"],
                temperature_c=tick["temperature_c"],
                power_draw_w=tick["power_draw_w"],
                comm_delay_ms=tick["comm_delay_ms"],
                sensor_latency_ms=tick["sensor_latency_ms"],
            ))
        ws_manager.broadcast_nowait({"type": "digital_twin_tick", "tick": tick})
        await asyncio.sleep(TICK_SECONDS)


async def start_digital_twin():
    global _task
    if _task is None:
        _task = asyncio.create_task(_loop())


async def stop_digital_twin():
    global _task
    if _task is not None:
        _task.cancel()
        _task = None


@router.get("/latest")
def latest(limit: int = 60):
    with engine.connect() as conn:
        rows = conn.execute(select(telemetry).order_by(desc(telemetry.c.id)).limit(limit)).fetchall()
    return [dict(r._mapping) for r in rows]
