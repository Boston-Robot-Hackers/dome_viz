#!/usr/bin/env python3
# floor_plan — clean an occupancy grid into a floor, wall segments and clutter
# Author: Pito Salas and Claude Code
# Version: 2
# Created: 2026-11-14
# Updated: 2026-11-16
# Open Source Under MIT license
"""Turn slam_toolbox's `/map` into what the page draws.

Each update:

1. `classify`: occupancy percent -> wall / free / unknown, by threshold.
2. `remove_wall_specks`: wall blobs under MIN_WALL_BLOB_CELLS (8-connected)
   become free; `fill_single_holes`: an unknown cell with three or four free
   neighbours becomes free.
3. Wall cells -> points at cell centres in `map` metres, fitted to straight
   lines by `wall_fit`. Points no line uses are clutter.

**Steady walls.** A `FloorPlanner` lives for one run and remembers the last
fit, so the page doesn't flicker as SLAM refines the map every few seconds:

- The room's main direction is re-estimated on every map until there is
  enough wall to trust it (MIN_LOCK_WALL_CELLS cells, or MIN_LOCK_WALL_M of
  fitted wall), then held. Locking on an early, tiny map would tilt every
  wall for the rest of the run. A changed direction drops the previous lines,
  which were fitted in the old frame.
- A new line that matches a previous one (same axis, level within the line
  band, overlapping span) is replaced by the previous one, unless a wall cell
  changed inside the previous line's footprint.

Grids are in `OccupancyGrid` order: row-major, row 0 at the lowest y. The
map's origin is taken to have zero yaw, as slam_toolbox publishes it.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np

from dome_viz.wall_fit import (
    LINE_BAND_M,
    MAX_GAP_M,
    MIN_LINE_POINTS,
    fit_lines,
    main_direction,
    rotate,
    snap_corners,
    to_segment,
)

UNKNOWN, FREE, WALL = 0, 1, 2
FREE_BELOW_PCT = 25
WALL_ABOVE_PCT = 65
MIN_WALL_BLOB_CELLS = 4
MIN_LOCK_WALL_CELLS = 200
MIN_LOCK_WALL_M = 3.0
NEIGHBOURS_8 = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc]


@dataclass(frozen=True)
class OccupancyData:
    """`OccupancyGrid` contents; `cells` are -1 (unknown) or 0-100 percent."""

    width: int
    height: int
    resolution_m: float
    origin_xy_m: tuple
    cells: Sequence


@dataclass
class FloorPlan:
    """`floor` is height x width uint8, FREE or UNKNOWN (wall cells are FREE).

    `walls` are [x1, y1, x2, y2] in `map` metres. `wall_cells_xy_m` (the
    occupied cells under the walls) and `clutter_xy_m` (the rest) are N x 2,
    also in `map` metres; together they are every occupied cell.
    `angle_rad` is the room's main wall direction, 0 to pi/2, and 0.0 until
    the planner has one.
    """

    floor: np.ndarray
    walls: list
    wall_cells_xy_m: np.ndarray
    clutter_xy_m: np.ndarray
    origin_xy_m: tuple
    resolution_m: float
    angle_rad: float


def classify(occupancy: OccupancyData) -> np.ndarray:
    expected = occupancy.width * occupancy.height
    if len(occupancy.cells) != expected:
        raise ValueError(
            f"map has {len(occupancy.cells)} cells, expected {expected} "
            f"({occupancy.width} x {occupancy.height})"
        )
    shape = (occupancy.height, occupancy.width)
    values = np.asarray(occupancy.cells, dtype=np.int16).reshape(shape)
    grid = np.full(shape, UNKNOWN, dtype=np.uint8)
    grid[(values >= 0) & (values < FREE_BELOW_PCT)] = FREE
    grid[values > WALL_ABOVE_PCT] = WALL
    return grid


def wall_blob(grid: np.ndarray, seed: tuple, seen: np.ndarray) -> list:
    """The 8-connected wall cells reachable from `seed`, marking them `seen`."""
    height, width = grid.shape
    blob, queue = [], deque([seed])
    seen[seed] = True
    while queue:
        row, col = queue.popleft()
        blob.append((row, col))
        for d_row, d_col in NEIGHBOURS_8:
            near = (row + d_row, col + d_col)
            is_inside = 0 <= near[0] < height and 0 <= near[1] < width
            if is_inside and not seen[near] and grid[near] == WALL:
                seen[near] = True
                queue.append(near)
    return blob


def remove_wall_specks(grid: np.ndarray) -> None:
    """Turn wall blobs smaller than MIN_WALL_BLOB_CELLS into free, in place."""
    seen = np.zeros(grid.shape, dtype=bool)
    for seed in zip(*np.nonzero(grid == WALL), strict=True):
        if seen[seed]:
            continue
        blob = wall_blob(grid, seed, seen)
        if len(blob) < MIN_WALL_BLOB_CELLS:
            grid[tuple(np.array(blob).T)] = FREE


def fill_single_holes(grid: np.ndarray) -> None:
    """An unknown cell with at least three free neighbours (of four) is free."""
    padded = np.pad(grid, 1, constant_values=UNKNOWN)
    free_neighbours = (
        (padded[:-2, 1:-1] == FREE).astype(int)
        + (padded[2:, 1:-1] == FREE)
        + (padded[1:-1, :-2] == FREE)
        + (padded[1:-1, 2:] == FREE)
    )
    grid[(grid == UNKNOWN) & (free_neighbours >= 3)] = FREE


def wall_points(grid: np.ndarray, occupancy: OccupancyData) -> np.ndarray:
    """Centres of the wall cells, N x 2 in `map` metres."""
    rows, cols = np.nonzero(grid == WALL)
    origin_x, origin_y = occupancy.origin_xy_m
    resolution = occupancy.resolution_m
    return np.column_stack(
        (origin_x + (cols + 0.5) * resolution, origin_y + (rows + 0.5) * resolution)
    )


def cell_keys(points: np.ndarray, resolution_m: float) -> set:
    """Map-frame cell indices of points, comparable across a growing map."""
    return set(map(tuple, np.floor(points / resolution_m).astype(int).tolist()))


class FloorPlanner:
    """Fits successive maps of one run, holding direction and unchanged walls."""

    def __init__(self):
        self.angle_rad: float | None = None
        self.is_direction_locked = False
        self.lines: list = []
        self.wall_keys: set = set()

    def update(self, occupancy: OccupancyData) -> FloorPlan:
        grid = classify(occupancy)
        remove_wall_specks(grid)
        fill_single_holes(grid)
        points = wall_points(grid, occupancy)
        resolution = occupancy.resolution_m
        if not self.is_direction_locked and len(points) >= MIN_LINE_POINTS:
            angle_rad = main_direction(points, resolution)
            if angle_rad != self.angle_rad:
                self.lines = []
            self.angle_rad = angle_rad
        lines, used = [], np.zeros(len(points), dtype=bool)
        if self.angle_rad is not None:
            lines, used = fit_lines(rotate(points, -self.angle_rad), resolution)
            fitted_m = sum(line.end - line.start for line in lines)
            if len(points) >= MIN_LOCK_WALL_CELLS or fitted_m >= MIN_LOCK_WALL_M:
                self.is_direction_locked = True
        keys = cell_keys(points, resolution)
        lines = self.keep_steady(lines, keys, resolution)
        snap_corners(lines)
        self.lines, self.wall_keys = lines, keys
        return FloorPlan(
            floor=np.where(grid == UNKNOWN, UNKNOWN, FREE).astype(np.uint8),
            walls=[to_segment(line, self.angle_rad) for line in lines],
            wall_cells_xy_m=points[used],
            clutter_xy_m=points[~used],
            origin_xy_m=tuple(occupancy.origin_xy_m),
            resolution_m=resolution,
            angle_rad=0.0 if self.angle_rad is None else self.angle_rad,
        )

    def keep_steady(self, lines: list, keys: set, resolution_m: float) -> list:
        """Swap each new line for its previous match if the cells under it held."""
        if not self.lines:
            return lines
        changed = np.array(sorted(self.wall_keys ^ keys), dtype=float).reshape(-1, 2)
        changed = rotate((changed + 0.5) * resolution_m, -self.angle_rad)
        unused = list(self.lines)
        steady = []
        for line in lines:
            previous = next((old for old in unused if is_match(old, line)), None)
            if previous is None or is_disturbed(previous, changed):
                steady.append(line)
            else:
                unused.remove(previous)
                steady.append(replace(previous))
        return steady


def is_match(old, new) -> bool:
    return (
        old.axis == new.axis
        and abs(old.level - new.level) <= LINE_BAND_M
        and old.start <= new.end
        and new.start <= old.end
    )


def is_disturbed(line, changed: np.ndarray) -> bool:
    """True if any changed wall cell (rotated frame) lies in `line`'s footprint."""
    level = changed[:, line.axis]
    along = changed[:, 1 - line.axis]
    in_band = np.abs(level - line.level) <= LINE_BAND_M
    in_span = (along >= line.start - MAX_GAP_M) & (along <= line.end + MAX_GAP_M)
    return bool((in_band & in_span).any())
