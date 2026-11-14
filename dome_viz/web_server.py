#!/usr/bin/env python3
# web_server — serves the page and one websocket on the local network
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license
"""aiohttp server for the page, in its own thread with its own asyncio loop.

- `GET /` is `index.html`; `/static/...` is the rest of `static_dir`.
- `GET /ws` is the websocket. A new page first gets `on_connect()`'s
  messages (the view's snapshot), then every broadcast.
- The page sends one kind of message, `{"type": "camera", "is_on": bool}`.
  `on_camera_change(is_wanted)` is called only when the number of pages with
  the camera on goes from zero to one or back, including when such a page
  closes. Camera JPEGs go only to those pages, as binary frames.

**Each page has its own outgoing queue**, filled synchronously on the loop
and drained by that page's writer task. So the snapshot always arrives before
later deltas, and a slow page never holds up the others.

`broadcast` and `send_camera` may be called from any thread. The callbacks
run on the server's thread.
"""

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from aiohttp import WSMsgType, web

START_TIMEOUT_S = 5.0
HEARTBEAT_S = 10.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ServerConfig:
    static_dir: Path
    host: str
    port: int


@dataclass
class Page:
    """One open websocket: its outgoing queue and whether it shows the camera."""

    socket: web.WebSocketResponse
    outbox: asyncio.Queue = field(default_factory=asyncio.Queue)
    is_camera_on: bool = False


class WebServer:
    """Start with `start()`, stop with `stop()`; see the module docstring."""

    def __init__(
        self,
        config: ServerConfig,
        on_connect: Callable[[], list],
        on_camera_change: Callable[[bool], None],
    ):
        self.config = config
        self.on_connect = on_connect
        self.on_camera_change = on_camera_change
        self.pages: list = []
        self.loop = asyncio.new_event_loop()
        self.runner: web.AppRunner | None = None
        self.thread: threading.Thread | None = None
        self.started = threading.Event()
        self.start_error: BaseException | None = None

    def start(self) -> None:
        """Serve in a background thread; raise if the server could not bind."""
        self.thread = threading.Thread(target=self.run, name="web_server")
        self.thread.start()
        if not self.started.wait(START_TIMEOUT_S):
            raise TimeoutError(f"web server did not start in {START_TIMEOUT_S} s")
        if self.start_error is not None:
            self.thread.join()
            raise RuntimeError(
                f"web server failed on {self.config.host}:{self.config.port}"
            ) from self.start_error

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

    def broadcast(self, messages: list) -> None:
        """Queue JSON messages for every open page."""
        texts = [json.dumps(message) for message in messages]
        self.loop.call_soon_threadsafe(self.enqueue, texts, False)

    def send_camera(self, jpeg: bytes) -> None:
        """Queue one camera frame for the pages showing the camera."""
        self.loop.call_soon_threadsafe(self.enqueue, [jpeg], True)

    def enqueue(self, items: list, is_camera: bool) -> None:
        for page in self.pages:
            if page.is_camera_on or not is_camera:
                for item in items:
                    page.outbox.put_nowait(item)

    def run(self) -> None:
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.open())
        except OSError as error:
            self.start_error = error
            self.started.set()
            self.loop.close()
            return
        self.started.set()
        self.loop.run_forever()
        self.loop.run_until_complete(self.close())
        self.loop.close()

    async def open(self) -> None:
        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/ws", self.handle_socket)
        app.router.add_static("/static", self.config.static_dir)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        config = self.config
        await web.TCPSite(self.runner, config.host, config.port).start()
        logger.info(f"serving {config.static_dir} on {config.host}:{config.port}")

    async def close(self) -> None:
        for page in list(self.pages):
            await page.socket.close()
        await self.runner.cleanup()

    async def handle_index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(self.config.static_dir / "index.html")

    async def handle_socket(self, request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse(heartbeat=HEARTBEAT_S)
        await socket.prepare(request)
        page = Page(socket)
        for message in self.on_connect():
            page.outbox.put_nowait(json.dumps(message))
        self.pages.append(page)
        writer = asyncio.create_task(self.write(page))
        try:
            async for frame in socket:
                if frame.type == WSMsgType.TEXT:
                    self.handle_page_message(page, frame.data)
        finally:
            writer.cancel()
            self.set_camera(page, is_on=False)
            self.pages.remove(page)
        return socket

    async def write(self, page: Page) -> None:
        while True:
            item = await page.outbox.get()
            try:
                if isinstance(item, bytes):
                    await page.socket.send_bytes(item)
                else:
                    await page.socket.send_str(item)
            except ConnectionResetError:
                logger.info("page closed while a message was being sent to it")
                return

    def handle_page_message(self, page: Page, text: str) -> None:
        try:
            message = json.loads(text)
            is_on = message["is_on"]
            is_camera = message["type"] == "camera" and isinstance(is_on, bool)
        except (ValueError, KeyError, TypeError):
            is_camera = False
        if not is_camera:
            logger.warning(f"ignoring unexpected page message: {text[:200]!r}")
            return
        self.set_camera(page, is_on)

    def set_camera(self, page: Page, is_on: bool) -> None:
        was_wanted = any(other.is_camera_on for other in self.pages)
        page.is_camera_on = is_on
        is_wanted = any(other.is_camera_on for other in self.pages)
        if is_wanted != was_wanted:
            self.on_camera_change(is_wanted)
