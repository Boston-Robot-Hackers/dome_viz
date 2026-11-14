#!/usr/bin/env python3
# test_run_history — trail and graph series: thinning, caps, deltas, corrections
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license

import math

import pytest

from dome_viz.run_history import (
    SERIES_STEP_S,
    TRAIL_MAX_POINTS,
    TRAIL_STEP_M,
    History,
    Pose2D,
    RunSeries,
    Trail,
    compose,
    distance_step,
)

IDENTITY = Pose2D(0.0, 0.0, 0.0)


def at(x_m: float, y_m: float = 0.0) -> Pose2D:
    return Pose2D(x_m, y_m, 0.0)


def test_compose_rotates_then_translates():
    pose = compose(Pose2D(1.0, 2.0, math.pi / 2), at(1.0))
    assert pose.x_m == pytest.approx(1.0)
    assert pose.y_m == pytest.approx(3.0)
    assert pose.yaw_rad == pytest.approx(math.pi / 2)


def test_trail_skips_sub_threshold_moves():
    trail = Trail()
    trail.add(at(0.0), IDENTITY)
    assert trail.add(at(TRAIL_STEP_M / 2), IDENTITY) is None
    message = trail.add(at(TRAIL_STEP_M * 2), IDENTITY)
    assert message["points"] == [[TRAIL_STEP_M * 2, 0.0]]
    assert len(trail.history.points) == 2


def test_history_drops_oldest_past_cap():
    history = History(3, 1.0, distance_step)
    for x_m in range(5):
        history.add((float(x_m), 0.0))
    assert list(history.points) == [(2.0, 0.0), (3.0, 0.0), (4.0, 0.0)]
    assert history.take_unsent() == list(history.points)


def test_trail_cap_is_told_to_the_page():
    assert Trail().snapshot()["max_points"] == TRAIL_MAX_POINTS


def test_first_pose_sends_full_trail():
    message = Trail().add(at(1.0), IDENTITY)
    assert message["is_full"]
    assert message["points"] == [[1.0, 0.0]]


def test_changed_map_to_odom_shifts_every_point():
    trail = Trail()
    trail.add(at(0.0), IDENTITY)
    trail.add(at(1.0), IDENTITY)
    corrected = Pose2D(0.5, -0.25, 0.0)
    message = trail.add(at(1.0), corrected)
    assert message["is_full"]
    assert message["points"] == [[0.5, -0.25], [1.5, -0.25]]


def test_tiny_map_to_odom_change_sends_only_new_points():
    trail = Trail()
    trail.add(at(0.0), IDENTITY)
    message = trail.add(at(1.0), Pose2D(0.01, 0.0, 0.0))
    assert not message["is_full"]
    assert len(message["points"]) == 1


def test_new_page_gets_full_trail_then_only_new_points():
    trail = Trail()
    trail.add(at(0.0), IDENTITY)
    trail.add(at(1.0), IDENTITY)
    trail.history.add((2.0, 0.0))  # recorded, not yet broadcast
    snapshot = trail.snapshot()
    assert snapshot["is_full"]
    assert snapshot["points"] == [[0.0, 0.0], [1.0, 0.0]]
    delta = trail.add(at(3.0), IDENTITY)
    assert delta["points"] == [[2.0, 0.0], [3.0, 0.0]]


def test_series_thinned_to_one_point_per_step():
    series = RunSeries(start_s=100.0)
    assert series.add({"speed_mps": 0.1}, 100.0) is not None
    assert series.add({"speed_mps": 0.2}, 100.0 + SERIES_STEP_S / 2) is None
    delta = series.add({"speed_mps": 0.3}, 100.0 + SERIES_STEP_S)
    assert delta["series"] == {"speed_mps": [[SERIES_STEP_S, 0.3]]}


def test_series_snapshot_has_every_series():
    series = RunSeries(start_s=0.0)
    series.add({"battery_pct": 80.0, "power_w": 6.5}, 1.0)
    snapshot = series.snapshot()
    assert snapshot["is_full"]
    assert snapshot["series"]["battery_pct"] == [[1.0, 80.0]]
    assert snapshot["series"]["objects"] == []
