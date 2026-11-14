#!/usr/bin/env python3
# wall_lines — fit straight wall segments to occupancy-grid wall cells
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-13
# Updated: 2026-11-13
# Open Source Under MIT license
"""Turn scattered wall cells into a few straight segments, floor-plan style.

First try for the TF01.1 mockup; TF01.3's floor_plan.py will own the real one.

1. Find the room's main wall direction: the rotation (0-90 degrees) at which
   wall points pile up most sharply into rows and columns.
2. In that rotated frame, take horizontal then vertical lines greedily: the
   densest row of points, split into runs wherever there's a gap, keeping
   runs long enough to be walls. Points used by a line are removed.
3. Close corners: an endpoint near a perpendicular segment is moved onto it.
4. Rotate everything back. Points no line explains are returned as clutter.

numpy only, no ROS.
"""

import math

import numpy as np

ANGLE_STEP_DEG = 1.0
LINE_BAND_M = 0.12  # points within this of a line belong to it
MIN_LINE_POINTS = 6
MIN_SEGMENT_M = 0.30
MAX_GAP_M = 0.30  # a gap wider than this splits a wall (doorways)
CORNER_SNAP_M = 0.30


def rotate(points: np.ndarray, angle: float) -> np.ndarray:
    cos, sin = math.cos(angle), math.sin(angle)
    return points @ np.array([[cos, sin], [-sin, cos]])


def main_direction(points: np.ndarray, resolution: float) -> float:
    """Rotation (rad) that best lines the points up with the x and y axes."""
    best_angle, best_score = 0.0, -1.0
    for degrees in np.arange(0.0, 90.0, ANGLE_STEP_DEG):
        turned = rotate(points, -math.radians(degrees))
        score = 0.0
        for axis in (0, 1):
            bins = np.floor(turned[:, axis] / resolution).astype(int)
            counts = np.bincount(bins - bins.min())
            score += float((counts.astype(float) ** 2).sum())
        if score > best_score:
            best_angle, best_score = math.radians(degrees), score
    return best_angle


def runs_along(values: np.ndarray) -> list:
    """Split 1-D positions into (start, end, indices) runs at big gaps."""
    order = np.argsort(values)
    ordered = values[order]
    breaks = np.nonzero(np.diff(ordered) > MAX_GAP_M)[0]
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [len(ordered) - 1]))
    return [
        (ordered[s], ordered[e], order[s : e + 1])
        for s, e in zip(starts, ends, strict=True)
    ]


def take_lines(points: np.ndarray, used: np.ndarray, axis: int, res: float) -> list:
    """Greedy lines of constant coordinate `axis` (1: horizontal, 0: vertical).

    Points in a kept segment are marked in `used`. Points in a band whose runs
    are too short are only skipped for the rest of this pass, so the other
    direction can still use them, and they end up as clutter otherwise.
    """
    segments = []
    along = 1 - axis
    tried = np.zeros(len(points), dtype=bool)
    while True:
        free = ~used & ~tried
        if free.sum() < MIN_LINE_POINTS:
            return segments
        bins = np.round(points[free, axis] / res).astype(int)
        values, counts = np.unique(bins, return_counts=True)
        if counts.max() < MIN_LINE_POINTS:
            return segments
        centre = values[counts.argmax()] * res
        band = free & (np.abs(points[:, axis] - centre) <= LINE_BAND_M)
        level = float(np.median(points[band, axis]))
        band_idx = np.nonzero(free & (np.abs(points[:, axis] - level) <= LINE_BAND_M))[
            0
        ]
        tried[band_idx] = True
        for start, end, members in runs_along(points[band_idx, along]):
            if end - start >= MIN_SEGMENT_M and len(members) >= MIN_LINE_POINTS:
                segment = [0.0] * 4
                segment[axis], segment[axis + 2] = level, level
                segment[along], segment[along + 2] = start, end
                segments.append(segment)
                used[band_idx[members]] = True


def snap_corners(horizontal: list, vertical: list) -> None:
    """Move endpoints that stop just short of (or overshoot) a crossing wall."""
    for h in horizontal:  # [x1, y, x2, y]
        for v in vertical:  # [x, y1, x, y2]
            x, y = v[0], h[1]
            near_v_span = (
                min(v[1], v[3]) - CORNER_SNAP_M <= y <= max(v[1], v[3]) + CORNER_SNAP_M
            )
            if not near_v_span:
                continue
            for i in (0, 2):
                if abs(h[i] - x) <= CORNER_SNAP_M:
                    h[i] = x
                    for j in (1, 3):
                        if abs(v[j] - y) <= CORNER_SNAP_M:
                            v[j] = y


def fit_walls(points: np.ndarray, resolution: float) -> tuple:
    """Wall points (N x 2, metres) -> (segments [[x1, y1, x2, y2]], clutter)."""
    if len(points) < MIN_LINE_POINTS:
        return [], points
    angle = main_direction(points, resolution)
    turned = rotate(points, -angle)
    used = np.zeros(len(points), dtype=bool)
    horizontal = take_lines(turned, used, 1, resolution)
    vertical = take_lines(turned, used, 0, resolution)
    snap_corners(horizontal, vertical)
    segments = []
    for x1, y1, x2, y2 in horizontal + vertical:
        (a, b), (c, d) = rotate(np.array([[x1, y1], [x2, y2]]), angle)
        segments.append([round(float(v), 3) for v in (a, b, c, d)])
    return segments, points[~used]
