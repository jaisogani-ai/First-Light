"""WebSocket broadcast for pipeline runs, verification results, and Digital Twin telemetry.

Routes are sync (`def`, not `async def`) so DB calls stay simple; broadcast_nowait hands the
send off to the main event loop via run_coroutine_threadsafe.
"""

import asyncio


class WSManager:
    def __init__(self):
        self._connections: set = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, ws) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws) -> None:
        self._connections.discard(ws)

    async def _broadcast(self, message: dict) -> None:
        dead = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    def broadcast_nowait(self, message: dict) -> None:
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcast(message), self._loop)


ws_manager = WSManager()
