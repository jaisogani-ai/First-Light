"""FastAPI application entry point. Run with: uvicorn backend.main:app --reload"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from backend.db import init_db
from backend.routers import attacks, commands, evaluation, metrics, pipeline, profiles, replay, telemetry
from backend.ws_manager import ws_manager
from db.seed import seed as seed_profiles

REPO_ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_profiles()
    ws_manager.set_loop(asyncio.get_running_loop())
    await telemetry.start_digital_twin()
    yield
    await telemetry.stop_digital_twin()


app = FastAPI(title="First Light — Proof-Carrying Commands for NASA cFS", lifespan=lifespan)

app.include_router(commands.router)
app.include_router(pipeline.router)
app.include_router(profiles.router)
app.include_router(replay.router)
app.include_router(attacks.router)
app.include_router(telemetry.router)
app.include_router(evaluation.router)
app.include_router(metrics.router)


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
