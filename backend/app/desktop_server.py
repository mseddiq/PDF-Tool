"""Loopback desktop server with an orderly shutdown requested from the UI."""

import asyncio
import os
import uvicorn
from .main import app, SHUTDOWN_EVENT


async def serve():
    os.environ["STUDIO_DESKTOP"] = "1"
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=int(os.getenv("STUDIO_PORT", "8000")),
            access_log=False,
            log_level="warning",
            use_colors=False,
        )
    )

    async def watch():
        while not SHUTDOWN_EVENT.is_set():
            await asyncio.sleep(0.15)
        server.should_exit = True

    watcher = asyncio.create_task(watch())
    try:
        await server.serve()
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(serve())
