#!/usr/bin/env python3
# test_web_server — page, websocket snapshot and broadcast, camera toggle
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license

import asyncio
import json
import socket

import aiohttp
import pytest

from dome_viz.web_server import ServerConfig, WebServer

HOST = "127.0.0.1"
RECEIVE_TIMEOUT_S = 2.0
SNAPSHOT = [{"type": "status", "state": "live"}]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    (tmp_path / "index.html").write_text("<title>dome_viz</title>")
    (tmp_path / "app.js").write_text("// page script")
    camera_changes = []
    web_server = WebServer(
        ServerConfig(tmp_path, HOST, free_port()),
        on_connect=lambda: SNAPSHOT,
        on_camera_change=camera_changes.append,
    )
    web_server.camera_changes = camera_changes
    web_server.start()
    yield web_server
    web_server.stop()


def url(server: WebServer, path: str) -> str:
    return f"http://{HOST}:{server.config.port}{path}"


async def receive_json(page) -> dict:
    return json.loads(await page.receive_str(timeout=RECEIVE_TIMEOUT_S))


async def wait_for(condition) -> None:
    for _ in range(100):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition never became true")


def test_serves_index_and_static(server):
    async def fetch():
        async with aiohttp.ClientSession() as session:
            async with session.get(url(server, "/")) as index:
                assert "dome_viz" in await index.text()
            async with session.get(url(server, "/static/app.js")) as script:
                assert script.status == 200

    asyncio.run(fetch())


def test_binds_to_given_host(server):
    (address,) = server.runner.addresses
    assert address[:2] == (HOST, server.config.port)


def test_port_in_use_raises(server, tmp_path):
    clash = WebServer(
        ServerConfig(tmp_path, HOST, server.config.port), lambda: [], print
    )
    with pytest.raises(RuntimeError, match="failed on"):
        clash.start()


def test_two_pages_get_snapshot_then_broadcast(server):
    async def talk():
        async with aiohttp.ClientSession() as session:
            first = await session.ws_connect(url(server, "/ws"))
            second = await session.ws_connect(url(server, "/ws"))
            for page in (first, second):
                assert await receive_json(page) == SNAPSHOT[0]
            await wait_for(lambda: len(server.pages) == 2)
            server.broadcast([{"type": "robot", "x": 1.0}])
            for page in (first, second):
                assert (await receive_json(page))["type"] == "robot"

    asyncio.run(talk())


def test_camera_toggle_reaches_callback_and_only_camera_pages_get_frames(server):
    async def talk():
        async with aiohttp.ClientSession() as session:
            viewer = await session.ws_connect(url(server, "/ws"))
            other = await session.ws_connect(url(server, "/ws"))
            await receive_json(viewer)
            await receive_json(other)
            await viewer.send_str(json.dumps({"type": "camera", "is_on": True}))
            await wait_for(lambda: server.camera_changes == [True])
            server.send_camera(b"\xff\xd8jpeg")
            assert await viewer.receive_bytes(timeout=RECEIVE_TIMEOUT_S) == (
                b"\xff\xd8jpeg"
            )
            server.broadcast([{"type": "robot"}])
            assert (await receive_json(other))["type"] == "robot"
            await viewer.close()
            await wait_for(lambda: server.camera_changes == [True, False])

    asyncio.run(talk())


def test_unexpected_page_message_is_ignored(server, caplog):
    async def talk():
        async with aiohttp.ClientSession() as session:
            page = await session.ws_connect(url(server, "/ws"))
            await receive_json(page)
            await page.send_str("not json")
            await wait_for(lambda: "unexpected page message" in caplog.text)

    asyncio.run(talk())
    assert server.camera_changes == []
