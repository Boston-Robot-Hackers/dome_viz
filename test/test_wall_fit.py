#!/usr/bin/env python3
# test_wall_fit — straight-line fitting of wall points
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license

import math

import numpy as np

from dome_viz.wall_fit import (
    HORIZONTAL,
    VERTICAL,
    Line,
    fit_lines,
    main_direction,
    snap_corners,
    to_segment,
)

RESOLUTION_M = 0.05


def wall_run(start_xy_m, end_xy_m):
    """Cell-centre points every RESOLUTION_M from start to end, inclusive."""
    start, end = np.array(start_xy_m), np.array(end_xy_m)
    count = round(np.linalg.norm(end - start) / RESOLUTION_M) + 1
    return np.linspace(start, end, count)


def test_straight_run_gives_one_line():
    lines, used = fit_lines(wall_run((0.0, 1.0), (2.0, 1.0)), RESOLUTION_M)
    assert len(lines) == 1
    assert lines[0].axis == HORIZONTAL
    assert math.isclose(lines[0].level, 1.0)
    assert used.all()


def test_gap_wider_than_doorway_splits_wall():
    points = np.vstack(
        (wall_run((0.0, 0.0), (1.0, 0.0)), wall_run((1.4, 0.0), (2.4, 0.0)))
    )
    lines, _ = fit_lines(points, RESOLUTION_M)
    assert len(lines) == 2


def test_gap_narrower_than_doorway_keeps_wall_whole():
    points = np.vstack(
        (wall_run((0.0, 0.0), (1.0, 0.0)), wall_run((1.2, 0.0), (2.2, 0.0)))
    )
    lines, _ = fit_lines(points, RESOLUTION_M)
    assert len(lines) == 1


def test_too_few_points_is_all_clutter():
    lines, used = fit_lines(wall_run((0.0, 0.0), (0.1, 0.0)), RESOLUTION_M)
    assert lines == []
    assert not used.any()


def test_snap_closes_a_corner():
    across = Line(HORIZONTAL, level=0.0, start=0.1, end=2.0)
    upright = Line(VERTICAL, level=0.0, start=0.15, end=2.0)
    snap_corners([across, upright])
    assert across.start == 0.0
    assert upright.start == 0.0


def test_snap_leaves_far_ends_alone():
    across = Line(HORIZONTAL, level=0.0, start=1.0, end=2.0)
    upright = Line(VERTICAL, level=0.0, start=1.0, end=2.0)
    snap_corners([across, upright])
    assert (across.start, upright.start) == (1.0, 1.0)


def test_main_direction_finds_rotation():
    angle = math.radians(30)
    square = np.vstack(
        [
            wall_run((0.0, 0.0), (3.0, 0.0)),
            wall_run((0.0, 2.0), (3.0, 2.0)),
            wall_run((0.0, 0.0), (0.0, 2.0)),
            wall_run((3.0, 0.0), (3.0, 2.0)),
        ]
    )
    cos, sin = math.cos(angle), math.sin(angle)
    turned = square @ np.array([[cos, sin], [-sin, cos]])
    assert math.isclose(main_direction(turned, RESOLUTION_M), angle, abs_tol=0.02)


def test_to_segment_rotates_back():
    line = Line(HORIZONTAL, level=0.0, start=0.0, end=1.0)
    x1, y1, x2, y2 = to_segment(line, math.pi / 2)
    assert (x1, y1) == (0.0, 0.0)
    assert math.isclose(x2, 0.0, abs_tol=1e-3)
    assert math.isclose(y2, 1.0)
