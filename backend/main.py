"""FastAPI application entry point. Run with: uvicorn backend.main:app --reload"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.db import init_db
from backend.routers import (attacks, audit, commands, documents, evaluation, imports, mission_analytics,
                              mission_assistant, mission_status, metrics, missions as missions_router, orbit,
                              pipeline, plugins, profiles, replay, scientific_review,
                              spacecraft as spacecraft_router, telemetry_analysis, telemetry)
from backend.security import rate_limiter
from backend.ws_manager import ws_manager
from db.seed import seed as seed_profiles

REPO_ROOT = Path(__file__).resolve().parent.parent
RATE_LIMITER_PRUNE_SECONDS = 300

# Every backend.logs.log_event() call goes to the 'first_light.events' logger — this makes
# those structured events actually reach stdout (as one JSON line per event) instead of
# being silently dropped by Python's default "no handler configured" behavior.
logging.basicConfig(level=logging.INFO, format="%(message)s")


async def _prune_rate_limiter_periodically():
    while True:
        await asyncio.sleep(RATE_LIMITER_PRUNE_SECONDS)
        await asyncio.to_thread(rate_limiter.prune)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_profiles()
    ws_manager.set_loop(asyncio.get_running_loop())
    await telemetry.start_digital_twin()
    prune_task = asyncio.create_task(_prune_rate_limiter_periodically())
    yield
    prune_task.cancel()
    await telemetry.stop_digital_twin()


app = FastAPI(title="First Light — Proof-Carrying Commands for NASA cFS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(commands.router)
app.include_router(pipeline.router)
app.include_router(profiles.router)
app.include_router(replay.router)
app.include_router(attacks.router)
app.include_router(telemetry.router)
app.include_router(evaluation.router)
app.include_router(metrics.router)
app.include_router(audit.router)
app.include_router(orbit.router)
# mission_analytics.compare_router registers /api/missions/compare — must come before
# missions_router's GET /api/missions/{mission_id}, or "compare" would be parsed as a
# mission_id and 422 before ever reaching the compare route (FastAPI matches in include order).
app.include_router(mission_analytics.compare_router)
app.include_router(missions_router.router)
app.include_router(imports.router)
app.include_router(mission_analytics.router)
app.include_router(mission_assistant.router)
app.include_router(plugins.router)
app.include_router(mission_status.router)
app.include_router(scientific_review.router)
app.include_router(documents.router)
app.include_router(spacecraft_router.router)
app.include_router(telemetry_analysis.router)


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/")
async def index():
    return FileResponse(REPO_ROOT / "index.html")


@app.get("/app.js")
async def app_js():
    return FileResponse(REPO_ROOT / "app.js", media_type="application/javascript")


@app.get("/styles.css")
async def styles_css():
    return FileResponse(REPO_ROOT / "styles.css", media_type="text/css")
