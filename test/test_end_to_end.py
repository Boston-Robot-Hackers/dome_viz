#!/usr/bin/env python3
# test_end_to_end — fake messages in at the ROS side, JSON out at a websocket
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-15
# Updated: 2026-11-15
# Open Source Under MIT license
"""The one test that exercises the whole chain with nothing faked in between.

`BridgeNode` is built with its **real** `WebServer`, on a free port, and the
assertions are made by a websocket client that knows only the wire format. So
this covers the bridge's conversions, `ViewState`, the message shapes and the
server's per-page queueing together — the seams the per-module tests cannot
see.

Messages are handed to the callbacks directly rather than published, so no ROS
graph, discovery or timing is involved; TF is injected into the node's buffer.
"""

import asyncio
import json
import socket

import aiohttp
import pytest
import rclpy
from dome_semantic.class_profiles import TargetClassProfile
from dome_semantic_msgs.msg import SemanticTarget, SemanticTargetArray
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid

from dome_viz import bridge_node
from dome_viz.bridge_node import BridgeNode

HOST = "127.0.0.1"
RECEIVE_TIMEOUT_S = 3.0

PROFILES = {
    "can": TargetClassProfile(
        canonical_class="can",
        display_name="soda can",
        abbrev="CN",
        detector_labels=["can"],
        height_range_m=(0.1, 0.2),
        diameter_range_m=(0.05, 0.08),
        aspect_ratio_range=(1.5, 3.0),
        max_stationary_speed_mps=0.05,
    )
}


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module", autouse=True)
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node(monkeypatch):
    """The bridge with its real web server, forced onto a free port.

    `BridgeNode` reads host and port from ROS parameters, which a unit test
    cannot override without a separate context, so the config it builds is
    rewritten on the way through instead.
    """
    port = free_port()
    config = bridge_node.ServerConfig
    monkeypatch.setattr(
        bridge_node,
        "ServerConfig",
        lambda static_dir, host, given_port: config(static_dir, HOST, port),
    )
    bridge = BridgeNode()
    bridge.view.profiles = PROFILES
    bridge.port = port
    yield bridge
    bridge.destroy_node()


def a_map() -> OccupancyGrid:
    """A 4x3 grid: the bottom row free, the rest unknown."""
    grid = OccupancyGrid()
    grid.info.width, grid.info.height = 4, 3
    grid.info.resolution = 0.05
    grid.info.origin.position.x = -0.5
    grid.info.origin.position.y = -1.0
    grid.data = [0, 0, 0, 0] + [-1] * 8
    return grid


def a_target() -> SemanticTargetArray:
    target = SemanticTarget()
    target.target_id = "3"
    target.label = "can"
    target.pose.position.x = 1.25
    target.pose.position.y = -0.75
    target.observation_count = 9
    array = SemanticTargetArray()
    array.targets = [target]
    return array


def place_robot(node: BridgeNode) -> None:
    stamp = node.get_clock().now().to_msg()
    for parent, child, x_m, y_m in (
        ("map", "odom", 0.0, 0.0),
        ("odom", "base_footprint", 2.0, 0.5),
    ):
        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = parent
        transform.child_frame_id = child
        transform.transform.translation.x = x_m
        transform.transform.translation.y = y_m
        transform.transform.rotation.w = 1.0
        node.tf_buffer.set_transform(transform, "test")


async def collect(port: int, wanted: set) -> dict:
    """Open a page and read until every wanted message type has arrived."""
    found = {}
    async with aiohttp.ClientSession() as session:
        page = await session.ws_connect(f"http://{HOST}:{port}/ws")
        while not wanted <= set(found):
            text = await page.receive_str(timeout=RECEIVE_TIMEOUT_S)
            message = json.loads(text)
            found.setdefault(message["type"], message)
    return found


def test_a_page_sees_the_floor_plan_a_labelled_target_and_the_robot(node):
    """The whole chain: three ROS inputs, three messages on the wire."""
    node.take_map(a_map())
    node.take_targets(a_target())
    place_robot(node)
    node.push_pose()

    found = asyncio.run(collect(node.port, {"floor_plan", "targets", "robot"}))

    plan = found["floor_plan"]
    assert (plan["width"], plan["height"]) == (4, 3)
    assert plan["origin"] == [-0.5, -1.0]

    (entry,) = found["targets"]["targets"]
    assert entry["name"] == "soda can"  # from the class profile
    assert entry["id"] == "CN3"  # abbrev + target id
    assert entry["label"] == "can"  # raw class, for the page's icon
    assert (entry["x"], entry["y"]) == (1.25, -0.75)
    assert entry["observations"] == 9

    robot = found["robot"]
    assert (robot["x"], robot["y"]) == (2.0, 0.5)  # map -> odom -> footprint


def test_a_page_opened_late_still_gets_the_snapshot(node):
    """`on_connect` runs on the server's thread, so this also exercises the lock."""
    node.take_map(a_map())
    first = asyncio.run(collect(node.port, {"floor_plan"}))
    second = asyncio.run(collect(node.port, {"floor_plan", "status"}))
    assert first["floor_plan"]["floor"] == second["floor_plan"]["floor"]
    assert second["status"]["ages_s"]["map"] is not None
