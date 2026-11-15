#!/usr/bin/env python3
# test_bridge_node — topic callbacks, TF-less pose, camera subscription life
# Author: Pito Salas and Claude Code
# Version: 4
# Created: 2026-11-14
# Updated: 2026-11-15
# Open Source Under MIT license
"""The bridge with a fake web server in place of the real one.

`rclpy` is initialised for real (a node, timers and subscriptions need it)
but nothing publishes: every callback is called directly with a built
message, which is also how the pose timer is driven.
"""

import math
from pathlib import Path

import pytest
import rclpy
from dome_semantic_msgs.msg import SemanticTarget, SemanticTargetArray
from dome_telemetry_msgs.msg import BatteryStats
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.duration import Duration
from sensor_msgs.msg import CompressedImage, LaserScan

from dome_viz import bridge_node
from dome_viz.bridge_node import CAMERA_TOPIC, TF_STALE_S, BridgeNode


class FakeServer:
    """Stands in for `WebServer`: records instead of serving."""

    def __init__(self, config, on_connect, on_camera_change):
        self.config = config
        self.on_connect = on_connect
        self.on_camera_change = on_camera_change
        self.messages: list = []
        self.jpegs: list = []
        self.is_started = False

    def start(self) -> None:
        self.is_started = True

    def stop(self) -> None:
        self.is_started = False

    def broadcast(self, messages: list) -> None:
        self.messages.extend(messages)

    def send_camera(self, jpeg: bytes) -> None:
        self.jpegs.append(jpeg)


@pytest.fixture(scope="module", autouse=True)
def ros():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node(monkeypatch):
    monkeypatch.setattr(bridge_node, "WebServer", FakeServer)
    bridge = BridgeNode()
    yield bridge
    bridge.destroy_node()


def types_in(server: FakeServer) -> list:
    return [message["type"] for message in server.messages]


def only(server: FakeServer, type_name: str) -> dict:
    (found,) = [m for m in server.messages if m["type"] == type_name]
    return found


def a_map(width: int = 4, height: int = 3) -> OccupancyGrid:
    grid = OccupancyGrid()
    grid.info.width = width
    grid.info.height = height
    grid.info.resolution = 0.05
    grid.info.origin.position.x = -1.0
    grid.info.origin.position.y = -2.0
    grid.data = [0] * (width * height)
    return grid


def a_target(label: str = "can", target_id: str = "7") -> SemanticTargetArray:
    target = SemanticTarget()
    target.target_id = target_id
    target.label = label
    target.pose.position.x = 1.5
    target.pose.position.y = -0.5
    target.observation_count = 4
    array = SemanticTargetArray()
    array.targets = [target]
    return array


def a_transform(
    parent: str, child: str, x_m: float, y_m: float, stamp
) -> TransformStamped:
    transform = TransformStamped()
    transform.header.frame_id = parent
    transform.child_frame_id = child
    transform.header.stamp = stamp
    transform.transform.translation.x = x_m
    transform.transform.translation.y = y_m
    transform.transform.rotation.w = 1.0
    return transform


def place_robot(
    node: BridgeNode, x_m: float = 2.0, y_m: float = 1.0, age_s: float = 0.0
) -> None:
    """A `map -> odom -> base_footprint` chain, stamped `age_s` ago.

    Dynamic transforms rather than static ones, because `lookup` judges a
    transform by its stamp and a static transform carries no useful one.
    """
    stamp = (node.get_clock().now() - Duration(seconds=age_s)).to_msg()
    node.tf_buffer.set_transform(a_transform("map", "odom", 0.0, 0.0, stamp), "test")
    node.tf_buffer.set_transform(
        a_transform("odom", "base_footprint", x_m, y_m, stamp), "test"
    )


def test_map_becomes_a_floor_plan(node):
    node.take_map(a_map())
    plan = only(node.server, "floor_plan")
    assert (plan["width"], plan["height"]) == (4, 3)
    assert plan["origin"] == [-1.0, -2.0]
    assert plan["resolution_m"] == pytest.approx(0.05)


def test_targets_become_a_targets_message(node):
    """Profiles are emptied first, so this does not depend on which packages
    are installed; the labelled case is covered by `test_view_state` and
    `test_end_to_end`."""
    node.view.profiles = {}
    node.take_targets(a_target())
    entry = only(node.server, "targets")["targets"][0]
    assert entry["name"] == "can"
    assert entry["id"] == "CA7"
    assert entry["label"] == "can"
    assert (entry["x"], entry["y"]) == (1.5, -0.5)
    assert entry["observations"] == 4


def test_targets_are_labelled_from_the_installed_profiles(node):
    """End of the chain the lookup fix was for: a published `can` reads as
    "soda can · CN7" when the robot's profiles are available."""
    if not bridge_node.default_profile_path():
        pytest.skip("dome_vision_ros is not installed here")
    node.take_targets(a_target())
    entry = only(node.server, "targets")["targets"][0]
    assert (entry["name"], entry["id"]) == ("soda can", "CN7")


def battery_stats(percent: float, power_w: float) -> BatteryStats:
    stats = BatteryStats()
    stats.percent = percent
    stats.power_w = power_w
    return stats


def series_in(server: FakeServer) -> dict:
    """Every `run` message's points, gathered per series name."""
    gathered: dict = {}
    for message in server.messages:
        if message["type"] == "run":
            for name, points in message["series"].items():
                gathered.setdefault(name, []).extend(points)
    return gathered


def test_battery_and_odom_feed_the_run_graphs(node):
    node.take_battery(battery_stats(percent=80.0, power_w=12.5))
    odometry = Odometry()
    odometry.twist.twist.linear.x = 0.3
    odometry.twist.twist.linear.y = 0.4
    node.take_odom(odometry)
    series = series_in(node.server)
    assert series, f"expected a run message, got {types_in(node.server)}"
    assert [value for _, value in series["battery_pct"]] == [80.0]
    assert [value for _, value in series["power_w"]] == [12.5]
    assert [value for _, value in series["speed_mps"]] == [0.5]


def test_pose_is_skipped_when_tf_has_no_transform(node):
    node.push_pose()
    assert node.server.messages == []


def test_pose_is_pushed_once_tf_answers(node):
    place_robot(node, x_m=2.0, y_m=1.0)
    node.push_pose()
    robot = only(node.server, "robot")
    assert (robot["x"], robot["y"]) == (2.0, 1.0)
    assert robot["yaw"] == pytest.approx(0.0)


def test_scan_is_skipped_when_tf_has_no_transform(node):
    scan = LaserScan()
    scan.header.frame_id = "laser"
    scan.angle_increment = 0.01
    scan.range_min, scan.range_max = 0.1, 10.0
    scan.ranges = [1.0] * 10
    node.take_scan(scan)
    assert node.server.messages == []


def test_camera_subscription_lives_only_while_a_page_wants_it(node):
    assert node.camera_subscription is None
    node.on_camera_change(True)
    assert node.camera_subscription is None, "must wait for our own thread"

    node.reconcile_camera()
    assert node.camera_subscription is not None
    assert CAMERA_TOPIC.lstrip("/") in node.camera_subscription.topic_name

    node.on_camera_change(False)
    node.reconcile_camera()
    assert node.camera_subscription is None


def test_camera_frames_pass_through_untouched(node):
    image = CompressedImage()
    image.data = [0xFF, 0xD8, 0x42]
    node.take_camera(image)
    assert node.server.jpegs == [b"\xff\xd8\x42"]


def test_a_new_page_gets_a_snapshot(node):
    node.take_map(a_map())
    snapshot = node.server.on_connect()
    assert "floor_plan" in [message["type"] for message in snapshot]
    assert snapshot[-1]["type"] == "status"


def test_tick_reports_status(node):
    node.push_tick()
    status = only(node.server, "status")
    assert status["state"] == "not_connected"
    assert status["ages_s"]["map"] is None


def test_yaw_of_a_quarter_turn(node):
    place_robot(node)
    turned = a_transform(
        "odom", "base_footprint", 0.0, 0.0, node.get_clock().now().to_msg()
    )
    turned.transform.rotation.z = math.sin(math.pi / 4)
    turned.transform.rotation.w = math.cos(math.pi / 4)
    node.tf_buffer.set_transform(turned, "test")
    node.push_pose()
    assert only(node.server, "robot")["yaw"] == pytest.approx(math.pi / 2, abs=1e-3)


def test_profiles_are_keyed_by_the_label_the_robot_publishes(node, tmp_path):
    """The yaml keys by canonical_class; /semantic/targets sends the detector
    label, so `profiles` must join them through `detector_labels`."""
    path = tmp_path / "class_profiles.yaml"
    path.write_text(
        "class_profiles:\n"
        "  - canonical_class: soda can\n"
        "    abbrev: CN\n"
        '    detector_labels: ["can", "tin"]\n'
        "    height_range_m: [0.115, 0.130]\n"
        "    diameter_range_m: [0.060, 0.068]\n"
        "    aspect_ratio_range: [1.7, 2.1]\n"
        "    max_stationary_speed_mps: 0.02\n"
    )
    profiles = node.profiles(str(path))
    assert sorted(profiles) == ["can", "tin"]
    assert profiles["can"].canonical_class == "soda can"
    assert profiles["can"].abbrev == "CN"


def test_no_profile_path_gives_empty_profiles(node):
    assert node.profiles("") == {}


def test_the_robots_installed_profiles_are_found_by_default():
    """Not a mock: the real file, so a rename on the vision side shows up."""
    path = bridge_node.default_profile_path()
    if path:
        assert path.endswith("config/class_profiles.yaml")
        assert Path(path).is_file()


def test_a_stale_transform_is_treated_as_absent(node):
    """I01: a dead publisher's last transform is not the pose now.

    A `tf2` buffer keeps returning it, so the bridge used to draw a gone robot
    motionless but reported as live.
    """
    place_robot(node, age_s=TF_STALE_S + 3.0)
    node.push_pose()
    assert node.server.messages == []


def test_a_stale_pose_leaves_the_state_disconnected(node):
    """The whole point of rejecting stale TF: the page must say so."""
    place_robot(node, age_s=TF_STALE_S + 3.0)
    for _ in range(5):
        node.push_pose()
    node.push_tick()
    status = only(node.server, "status")
    assert status["ages_s"]["pose"] is None
    assert status["state"] == "not_connected"
