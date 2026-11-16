#!/usr/bin/env python3
# test_view_state — labels, lost targets, status, run start, laser, floor plan
# Author: Pito Salas and Claude Code
# Version: 4
# Created: 2026-11-14
# Updated: 2026-11-16
# Open Source Under MIT license

import base64
import math

import pytest
from dome_semantic.class_profiles import TargetClassProfile, parse_class_profiles

from dome_viz.floor_plan import OccupancyData
from dome_viz.run_history import Pose2D
from dome_viz.view_state import (
    LASER_PERIOD_S,
    LASER_RAY_STRIDE,
    LOST_TIMEOUT_S,
    QUIET_S,
    RUN_GAP_S,
    ScanData,
    TargetData,
    ViewState,
    name_and_id,
    target_entry,
    view_angle_rad,
)

CAN_PROFILE = {
    "canonical_class": "can",
    "display_name": "soda can",
    "abbrev": "CN",
    "height_range_m": (0.1, 0.14),
    "diameter_range_m": (0.05, 0.08),
    "aspect_ratio_range": (1.2, 2.5),
    "max_stationary_speed_mps": 0.05,
}
PROFILES = parse_class_profiles([CAN_PROFILE])
ORIGIN = Pose2D(0.0, 0.0, 0.0)


def can(last_seen_s: float) -> TargetData:
    return TargetData("1", "can", 1.0, 2.0, 3, last_seen_s)


def by_type(messages: list, message_type: str) -> list:
    return [message for message in messages if message["type"] == message_type]


def test_label_with_profile_uses_display_name_and_abbrev():
    assert name_and_id("can", "1", PROFILES) == ("soda can", "CN1")


def test_label_with_no_profile_falls_back_to_raw_label():
    assert name_and_id("bottle", "4", PROFILES) == ("bottle", "BO4")


def test_a_profile_with_no_display_name_uses_its_canonical_class():
    """The robot's real `class_profiles.yaml` sets no `display_name`.

    It carries `canonical_class: soda can` with `detector_labels: ["can"]`,
    and `/semantic/targets` publishes the detector label, so the readable name
    has to come from the canonical class.
    """
    profile = TargetClassProfile(
        canonical_class="soda can",
        abbrev="CN",
        detector_labels=["can"],
        height_range_m=(0.115, 0.130),
        diameter_range_m=(0.060, 0.068),
        aspect_ratio_range=(1.7, 2.1),
        max_stationary_speed_mps=0.02,
    )
    assert name_and_id("can", "1", {"can": profile}) == ("soda can", "CN1")


@pytest.mark.parametrize(
    ("ago_s", "is_lost"),
    [(LOST_TIMEOUT_S - 0.001, False), (LOST_TIMEOUT_S + 0.001, True)],
)
def test_lost_threshold(ago_s, is_lost):
    entry = target_entry(can(100.0), PROFILES, 100.0 + ago_s)
    assert entry["is_lost"] is is_lost


def test_target_entry_carries_age_and_position():
    entry = target_entry(can(100.0), PROFILES, 130.0)
    assert entry["seen_ago_s"] == 30.0
    assert (entry["x"], entry["y"], entry["observations"]) == (1.0, 2.0, 3)


def test_target_entry_carries_the_raw_label():
    """The page picks each object's icon and colour from the class, not the
    display name, so the raw label has to survive into the message."""
    entry = target_entry(can(100.0), PROFILES, 100.0)
    assert entry["label"] == "can"
    assert (entry["name"], entry["id"]) == ("soda can", "CN1")


def test_status_reports_source_never_heard_from():
    state = ViewState(PROFILES)
    status = state.status_message(10.0)
    assert status["state"] == "not_connected"
    assert status["ages_s"]["map"] is None
    assert status["run_s"] is None


def test_status_waits_for_map_then_goes_live():
    state = ViewState(PROFILES)
    state.on_speed(0.0, 10.0)
    assert state.status_message(11.0)["state"] == "waiting_for_map"
    state.on_map(OccupancyData(2, 2, 0.05, (0.0, 0.0), [0, 0, 0, 0]), 11.0)
    status = state.status_message(12.0)
    assert status["state"] == "live"
    assert status["ages_s"]["odom"] == 2.0
    assert status["run_s"] == 2.0


def test_status_not_connected_when_all_quiet():
    state = ViewState(PROFILES)
    state.on_speed(0.0, 10.0)
    assert state.status_message(10.0 + QUIET_S + 0.1)["state"] == "not_connected"


@pytest.mark.parametrize(
    ("gap_s", "is_new_run"), [(RUN_GAP_S - 1.0, False), (RUN_GAP_S + 1.0, True)]
)
def test_quiet_gap_starts_new_run(gap_s, is_new_run):
    state = ViewState(PROFILES)
    state.on_pose(Pose2D(0.0, 0.0, 0.0), ORIGIN, 0.0)
    state.on_pose(Pose2D(1.0, 0.0, 0.0), ORIGIN, 1.0)
    messages = state.on_speed(0.0, 1.0 + gap_s)
    assert bool(by_type(messages, "trail")) is is_new_run
    assert (state.run.start_s == 1.0 + gap_s) is is_new_run


def test_run_start_empties_trail():
    state = ViewState(PROFILES)
    state.on_pose(Pose2D(0.0, 0.0, 0.0), ORIGIN, 0.0)
    state.on_pose(Pose2D(1.0, 0.0, 0.0), ORIGIN, 1.0)
    messages = state.on_speed(0.0, 1.0 + RUN_GAP_S + 1.0)
    (trail,) = by_type(messages, "trail")
    assert trail["is_full"]
    assert trail["points"] == []


def test_pose_gives_robot_in_map():
    state = ViewState(PROFILES)
    messages = state.on_pose(Pose2D(1.0, 0.0, 0.0), Pose2D(0.0, 0.0, math.pi / 2), 0.0)
    (robot,) = by_type(messages, "robot")
    assert (robot["x"], robot["y"], robot["yaw"]) == (0.0, 1.0, 1.571)


def test_laser_drops_invalid_ranges_and_strides():
    state = ViewState(PROFILES)
    ranges = [1.0] * (LASER_RAY_STRIDE * 2)
    ranges[LASER_RAY_STRIDE] = float("inf")
    scan = ScanData(0.0, 0.01, 0.1, 10.0, ranges)
    (laser,) = by_type(state.on_scan(Pose2D(2.0, 0.0, 0.0), scan, 0.0), "laser")
    assert laser["origin"] == [2.0, 0.0]
    assert laser["hits"] == [[3.0, 0.0]]


def test_laser_rate_limited():
    state = ViewState(PROFILES)
    scan = ScanData(0.0, 0.01, 0.1, 10.0, [1.0])
    state.on_scan(ORIGIN, scan, 0.0)
    assert not by_type(state.on_scan(ORIGIN, scan, LASER_PERIOD_S / 2), "laser")
    assert by_type(state.on_scan(ORIGIN, scan, LASER_PERIOD_S), "laser")


def test_floor_plan_message_encodes_floor():
    state = ViewState(PROFILES)
    occupancy = OccupancyData(3, 1, 0.05, (1.0, 2.0), [-1, 0, 0])
    (plan,) = by_type(state.on_map(occupancy, 0.0), "floor_plan")
    assert (plan["width"], plan["height"], plan["origin"]) == (3, 1, [1.0, 2.0])
    assert list(base64.b64decode(plan["floor"])) == [0, 1, 1]
    assert plan["angle_rad"] == 0.0


def test_view_angle_is_the_smallest_turn():
    assert view_angle_rad(math.radians(10)) == pytest.approx(math.radians(10))
    assert view_angle_rad(math.radians(80)) == pytest.approx(math.radians(-10))
    assert view_angle_rad(math.pi / 4) == pytest.approx(math.pi / 4)


def test_targets_feed_objects_series():
    state = ViewState(PROFILES)
    messages = state.on_targets([can(0.0), can(0.0)], 0.0)
    (delta,) = [run for run in by_type(messages, "run") if not run["is_full"]]
    assert delta["series"] == {"objects": [[0.0, 2.0]]}


def test_snapshot_has_what_a_new_page_needs():
    state = ViewState(PROFILES)
    state.on_targets([can(0.0)], 0.0)
    state.on_pose(Pose2D(0.0, 0.0, 0.0), ORIGIN, 0.0)
    types = [message["type"] for message in state.snapshot(1.0)]
    assert types == ["robot", "targets", "trail", "run", "status"]
