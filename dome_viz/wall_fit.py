#!/usr/bin/env python3
# wall_fit — fit straight wall segments to occupancy-grid wall cells
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license
"""Turn scattered wall cells into a few straight lines, floor-plan style.

1. `main_direction`: the rotation (0-90 degrees) at which the wall points pile
   up most sharply into rows and columns, i.e. the room's own axes.
2. `fit_lines`: in that rotated frame, take horizontal then vertical lines
   greedily: the densest row of points, split into runs at gaps wider than a
   doorway, keeping runs long enough to be walls. Points a line uses are
   marked, and the rest are clutter.
3. `snap_corners`: an end that stops just short of (or overshoots) a crossing
   wall is moved onto it, so corners close.

Lines live in the rotated frame as `Line(axis, level, start, end)`, axis being
the coordinate held constant; `to_segment` rotates one back to `map` metres.
numpy only, no ROS.
"""

import math
from dataclasses import dataclass

import numpy as np

ANGLE_STEP_DEG = 1.0
LINE_BAND_M = 0.12  # points within this of a line belong to it
MIN_LINE_POINTS = 6
MIN_SEGMENT_M = 0.30
MAX_GAP_M = 0.30  # a gap wider than this splits a wall (doorways)
CORNER_SNAP_M = 0.30
HORIZONTAL, VERTICAL = 1, 0  # the axis a line holds constant


@dataclass
class Line:
    axis: int
    level: float
    start: float
    end: float

    def snap_end(self, value: float) -> None:
        if abs(self.start - value) <= CORNER_SNAP_M:
            self.start = value
        if abs(self.end - value) <= CORNER_SNAP_M:
            self.end = value

    def spans(self, value: float, margin_m: float) -> bool:
        return self.start - margin_m <= value <= self.end + margin_m


def rotate(points: np.ndarray, angle_rad: float) -> np.ndarray:
    """Rotate N x 2 points counter-clockwise by `angle_rad` about the origin."""
    cos, sin = math.cos(angle_rad), math.sin(angle_rad)
    return points @ np.array([[cos, sin], [-sin, cos]])


def main_direction(points: np.ndarray, resolution_m: float) -> float:
    """Rotation (rad, 0 to pi/2) that best lines the points up with x and y."""
    best_angle, best_score = 0.0, -1.0
    for degrees in np.arange(0.0, 90.0, ANGLE_STEP_DEG):
        turned = rotate(points, -math.radians(degrees))
        score = 0.0
        for axis in (0, 1):
            bins = np.floor(turned[:, axis] / resolution_m).astype(int)
            counts = np.bincount(bins - bins.min()).astype(float)
            score += float((counts**2).sum())
        if score > best_score:
            best_angle, best_score = math.radians(degrees), score
    return best_angle


def runs_along(values: np.ndarray) -> list:
    """Split 1-D positions into (start, end, indices) runs at gaps > MAX_GAP_M."""
    order = np.argsort(values)
    ordered = values[order]
    breaks = np.nonzero(np.diff(ordered) > MAX_GAP_M)[0]
    starts = np.concatenate(([0], breaks + 1))
    ends = np.concatenate((breaks, [len(ordered) - 1]))
    return [
        (float(ordered[first]), float(ordered[last]), order[first : last + 1])
        for first, last in zip(starts, ends, strict=True)
    ]


def take_lines(
    points: np.ndarray, used: np.ndarray, axis: int, resolution_m: float
) -> list:
    """Greedy lines holding coordinate `axis` constant.

    Points in a kept line are marked in `used`. Points in a band whose runs are
    too short are skipped only for the rest of this pass, so the other
    direction can still use them; otherwise they end up as clutter.
    """
    lines = []
    along = 1 - axis
    tried = np.zeros(len(points), dtype=bool)
    while True:
        free = ~used & ~tried
        if free.sum() < MIN_LINE_POINTS:
            return lines
        bins = np.round(points[free, axis] / resolution_m).astype(int)
        values, counts = np.unique(bins, return_counts=True)
        if counts.max() < MIN_LINE_POINTS:
            return lines
        centre = values[counts.argmax()] * resolution_m
        near_centre = free & (np.abs(points[:, axis] - centre) <= LINE_BAND_M)
        level = float(np.median(points[near_centre, axis]))
        band = np.nonzero(free & (np.abs(points[:, axis] - level) <= LINE_BAND_M))[0]
        tried[band] = True
        for start, end, members in runs_along(points[band, along]):
            if end - start >= MIN_SEGMENT_M and len(members) >= MIN_LINE_POINTS:
                lines.append(Line(axis, level, start, end))
                used[band[members]] = True


def fit_lines(points: np.ndarray, resolution_m: float) -> tuple:
    """Rotated-frame points (N x 2) -> (lines, mask of points the lines use)."""
    used = np.zeros(len(points), dtype=bool)
    if len(points) < MIN_LINE_POINTS:
        return [], used
    lines = take_lines(points, used, HORIZONTAL, resolution_m)
    lines += take_lines(points, used, VERTICAL, resolution_m)
    return lines, used


def snap_corners(lines: list) -> None:
    """Close corners: move ends near a crossing perpendicular line onto it."""
    horizontal = [line for line in lines if line.axis == HORIZONTAL]
    vertical = [line for line in lines if line.axis == VERTICAL]
    for across in horizontal:
        for upright in vertical:
            if upright.spans(across.level, CORNER_SNAP_M) and across.spans(
                upright.level, CORNER_SNAP_M
            ):
                across.snap_end(upright.level)
                upright.snap_end(across.level)


def to_segment(line: Line, angle_rad: float) -> list:
    """A rotated-frame line -> [x1, y1, x2, y2] in `map` metres."""
    if line.axis == HORIZONTAL:
        ends = np.array([[line.start, line.level], [line.end, line.level]])
    else:
        ends = np.array([[line.level, line.start], [line.level, line.end]])
    (x1, y1), (x2, y2) = rotate(ends, angle_rad)
    return [round(float(value), 3) for value in (x1, y1, x2, y2)]
