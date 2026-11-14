#!/usr/bin/env python3
# test_floor_plan — occupancy grid cleanup and steady wall segments
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license

import math
import pathlib

import numpy as np
import pytest
import yaml

from dome_viz.floor_plan import (
    FREE,
    MIN_WALL_BLOB_CELLS,
    UNKNOWN,
    WALL,
    FloorPlanner,
    OccupancyData,
    classify,
    fill_single_holes,
    remove_wall_specks,
    wall_blob,
)

RESOLUTION_M = 0.05
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def occupancy(percent: np.ndarray, origin_xy_m=(0.0, 0.0)) -> OccupancyData:
    height, width = percent.shape
    return OccupancyData(
        width, height, RESOLUTION_M, origin_xy_m, percent.ravel().tolist()
    )


def free_grid(rows: int, cols: int) -> np.ndarray:
    return np.zeros((rows, cols), dtype=int)


def draw(percent: np.ndarray, start_xy_m, end_xy_m) -> None:
    """Mark the cells along a line (origin 0, 0) as walls."""
    start, end = np.array(start_xy_m), np.array(end_xy_m)
    steps = int(np.linalg.norm(end - start) / RESOLUTION_M * 4) + 1
    for point in np.linspace(start, end, steps):
        col, row = np.floor(point / RESOLUTION_M).astype(int)
        percent[row, col] = 100


def load_pgm_map(name: str) -> OccupancyData:
    """A map_saver .pgm + .yaml (trinary) as OccupancyGrid data."""
    meta = yaml.safe_load((FIXTURES / f"{name}.yaml").read_text())
    _, width, height, _, pixels = (FIXTURES / f"{name}.pgm").read_bytes().split(
        maxsplit=4
    )
    shape = (int(height), int(width))
    darkness = (255 - np.frombuffer(pixels, np.uint8).reshape(shape)) / 255.0
    percent = np.full(shape, -1, dtype=int)
    percent[darkness > meta["occupied_thresh"]] = 100
    percent[darkness < meta["free_thresh"]] = 0
    return occupancy(np.flipud(percent), tuple(meta["origin"][:2]))


def speck_cells(grid: np.ndarray) -> int:
    seen = np.zeros(grid.shape, dtype=bool)
    total = 0
    for seed in zip(*np.nonzero(grid == WALL), strict=True):
        if not seen[seed]:
            blob = wall_blob(grid, seed, seen)
            total += len(blob) if len(blob) < MIN_WALL_BLOB_CELLS else 0
    return total


def test_classify_thresholds():
    percent = np.array([[-1, 0, 24, 25, 65, 66, 100]])
    grid = classify(occupancy(percent))
    expected = [UNKNOWN, FREE, FREE, UNKNOWN, UNKNOWN, WALL, WALL]
    assert grid[0].tolist() == expected


def test_classify_rejects_wrong_cell_count():
    bad = OccupancyData(3, 3, RESOLUTION_M, (0.0, 0.0), [0] * 8)
    with pytest.raises(ValueError, match="8 cells, expected 9"):
        classify(bad)


def test_speck_is_removed():
    percent = free_grid(10, 10)
    percent[5, 5] = 100
    grid = classify(occupancy(percent))
    remove_wall_specks(grid)
    assert grid[5, 5] == FREE


def test_wall_line_survives_cleanup():
    percent = free_grid(10, 10)
    percent[5, 1:9] = 100
    grid = classify(occupancy(percent))
    remove_wall_specks(grid)
    assert (grid[5, 1:9] == WALL).all()


def test_unknown_stays_unknown():
    percent = np.full((10, 10), -1)
    grid = classify(occupancy(percent))
    remove_wall_specks(grid)
    fill_single_holes(grid)
    assert (grid == UNKNOWN).all()


def test_single_hole_is_filled():
    percent = free_grid(5, 5)
    percent[2, 2] = -1
    grid = classify(occupancy(percent))
    fill_single_holes(grid)
    assert grid[2, 2] == FREE


def test_floor_marks_walls_as_seen():
    percent = free_grid(10, 10)
    percent[5, 1:9] = 100
    percent[0, :] = -1
    plan = FloorPlanner().update(occupancy(percent))
    assert set(np.unique(plan.floor)) == {UNKNOWN, FREE}
    assert (plan.floor[5, 1:9] == FREE).all()


def test_real_map_keeps_walls_and_drops_specks():
    occupancy_data = load_pgm_map("f36run6")
    raw = classify(occupancy_data)
    cleaned = raw.copy()
    remove_wall_specks(cleaned)
    assert speck_cells(raw) > 0
    assert speck_cells(cleaned) == 0
    kept = (raw == WALL).sum() - speck_cells(raw)
    assert (cleaned == WALL).sum() == kept
    assert FloorPlanner().update(occupancy_data).walls


def test_l_gives_two_segments_meeting_at_corner():
    percent = free_grid(60, 60)
    draw(percent, (0.5, 0.5), (2.5, 0.5))
    draw(percent, (0.5, 0.5), (0.5, 2.5))
    walls = FloorPlanner().update(occupancy(percent)).walls
    assert len(walls) == 2
    ends = [tuple(wall[:2]) for wall in walls] + [tuple(wall[2:]) for wall in walls]
    assert len(ends) - len(set(ends)) == 1


def test_rotated_room_segments_follow_its_angle():
    angle = math.radians(30)
    corners = np.array([[0.0, 0.0], [2.0, 0.0], [2.0, 1.5], [0.0, 1.5]])
    cos, sin = math.cos(angle), math.sin(angle)
    corners = corners @ np.array([[cos, sin], [-sin, cos]]) + [2.0, 0.5]
    percent = free_grid(100, 100)
    for index in range(4):
        draw(percent, corners[index], corners[(index + 1) % 4])
    walls = FloorPlanner().update(occupancy(percent)).walls
    assert len(walls) >= 4
    for x1, y1, x2, y2 in walls:
        heading = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 90
        assert abs(heading - 30) < 2


def test_refit_of_unchanged_map_is_identical():
    percent = free_grid(60, 60)
    draw(percent, (0.5, 0.5), (2.5, 0.5))
    draw(percent, (0.5, 0.5), (0.5, 2.5))
    planner = FloorPlanner()
    first = planner.update(occupancy(percent)).walls
    assert planner.update(occupancy(percent)).walls == first


def test_direction_is_held_once_enough_wall():
    planner = FloorPlanner()
    percent = free_grid(80, 80)
    draw(percent, (0.5, 0.5), (3.8, 0.5))
    planner.update(occupancy(percent))
    assert planner.is_direction_locked
    tilted = free_grid(80, 80)
    draw(tilted, (0.5, 0.5), (2.5, 1.6))
    planner.update(occupancy(tilted))
    assert planner.angle_rad == 0.0


def test_tiny_early_map_does_not_lock_direction():
    planner = FloorPlanner()
    early = free_grid(80, 80)
    angle = math.radians(29)
    tip_xy_m = (0.5 + 0.35 * math.cos(angle), 0.5 + 0.35 * math.sin(angle))
    draw(early, (0.5, 0.5), tip_xy_m)
    planner.update(occupancy(early))
    assert not planner.is_direction_locked
    room = free_grid(80, 80)
    for start, end in [((0.5, 0.5), (3.5, 0.5)), ((0.5, 0.5), (0.5, 3.0))]:
        draw(room, start, end)
    walls = planner.update(occupancy(room)).walls
    assert planner.angle_rad == 0.0
    for x1, y1, x2, y2 in walls:
        assert x1 == x2 or y1 == y2


def test_wall_away_from_a_change_keeps_its_ends():
    percent = free_grid(80, 80)
    draw(percent, (0.5, 0.5), (3.0, 0.5))
    planner = FloorPlanner()
    first = planner.update(occupancy(percent)).walls
    planner.lines[0].end = 2.9  # stand-in for a refit that would drift
    draw(percent, (0.5, 3.5), (3.0, 3.5))
    walls = planner.update(occupancy(percent)).walls
    assert len(walls) == len(first) + 1
    lower = next(wall for wall in walls if wall[1] < 1.0)
    assert lower[2] == 2.9


def test_wall_under_a_change_is_refitted():
    percent = free_grid(80, 80)
    draw(percent, (0.5, 0.5), (3.0, 0.5))
    planner = FloorPlanner()
    planner.update(occupancy(percent))
    planner.lines[0].end = 2.9
    draw(percent, (3.0, 0.5), (3.5, 0.5))
    walls = planner.update(occupancy(percent)).walls
    assert len(walls) == 1
    assert walls[0][2] > 3.4
