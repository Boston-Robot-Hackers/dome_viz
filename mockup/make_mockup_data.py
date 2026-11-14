#!/usr/bin/env python3
# make_mockup_data — build the TF01.1 layout mockup's data.js from a real run
# Author: Pito Salas and Claude Code
# Version: 2
# Created: 2026-11-13
# Updated: 2026-11-13
# Open Source Under MIT license
"""Write mockup/data.js for the static layout mockup (TF01.1).

Reads a run's bag and its saved semantic targets
(~/.dome/semantic_maps/<name>.json, if there is one), plus dome_semantic's
class profiles.

The floor plan is the bag's last /map. A bag without /map (e.g. f36run6)
gets one rebuilt from /scan along the robot's path (map -> odom ->
base_footprint -> laser). Cleanup is a throwaway first try (drop small wall
specks, fill one-cell holes); the real one is TF01.3's floor_plan.py.

Usage: make_mockup_data.py <map_name> <bag_dir> [<targets_name>]

<targets_name> picks a different saved targets file, e.g. a bag replay's.
"""

import json
import math
import pathlib
import sys
from collections import deque

import numpy as np
import rosbag2_py
import yaml
from nav_msgs.msg import OccupancyGrid
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import LaserScan
from series import run_series
from tf2_msgs.msg import TFMessage
from wall_lines import fit_walls

HOME = pathlib.Path.home()
SEMANTIC_DIR = HOME / ".dome" / "semantic_maps"
PROFILES = HOME / "ros2_ws" / "src" / "dome_semantic" / "config" / "class_profiles.yaml"
OUT = pathlib.Path(__file__).parent / "data.js"
# The viz01 drive recorded no battery data, and the UPS reader has logged none
# since 11-05; the run panel uses this real earlier log as a sample.
BATTERY_SAMPLE_LOG = HOME / ".dome" / "telemetry" / "10-23-telemetry"

UNKNOWN, FREE, WALL = 0, 1, 2
RESOLUTION_M = 0.05
MAX_RANGE_M = 6.0
MIN_WALL_BLOB = 4
WALL_HIT_RATIO = 0.3
MIN_WALL_HITS = 3
FREE_BELOW, WALL_ABOVE = 25, 65  # OccupancyGrid percent
TRAIL_STEP_M = 0.05
SCAN_STEP_M = 0.05
SCAN_STEP_RAD = math.radians(5)
LOST_AFTER_S = 5.0
LASER_IN_BASE = (-0.08, 0.0, -math.pi / 2)  # base_footprint -> laser, f36run6


def yaw_of(rotation) -> float:
    q = rotation
    return math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))


def compose(parent: tuple, child: tuple) -> tuple:
    px, py, pth = parent
    cx, cy, cth = child
    return (
        px + cx * math.cos(pth) - cy * math.sin(pth),
        py + cx * math.sin(pth) + cy * math.cos(pth),
        pth + cth,
    )


def angle_gap(a: float, b: float) -> float:
    return abs(math.atan2(math.sin(a - b), math.cos(a - b)))


def scan_points(scan: LaserScan, laser: tuple) -> tuple:
    """Beam endpoints in map, and points sampled along each beam (free space)."""
    ranges = np.asarray(scan.ranges)
    angles = scan.angle_min + scan.angle_increment * np.arange(len(ranges))
    valid = np.isfinite(ranges) & (ranges > scan.range_min) & (ranges < MAX_RANGE_M)
    ranges, angles = ranges[valid], angles[valid] + laser[2]
    ends = np.column_stack(
        (laser[0] + ranges * np.cos(angles), laser[1] + ranges * np.sin(angles))
    )
    steps = np.maximum((ranges / (RESOLUTION_M / 2)).astype(int), 1)
    beam = np.repeat(np.arange(len(ranges)), steps)
    fraction = (np.arange(steps.sum()) - np.repeat(np.cumsum(steps) - steps, steps)) / (
        np.repeat(steps, steps) + 1
    )
    along = np.column_stack(
        (
            laser[0] + ranges[beam] * fraction * np.cos(angles[beam]),
            laser[1] + ranges[beam] * fraction * np.sin(angles[beam]),
        )
    )
    return ends, along


def planar_transforms(message: TFMessage) -> dict:
    """{(parent, child): (x, y, yaw)} for each transform in a /tf message."""
    return {
        (tr.header.frame_id, tr.child_frame_id): (
            tr.transform.translation.x,
            tr.transform.translation.y,
            yaw_of(tr.transform.rotation),
        )
        for tr in message.transforms
    }


def read_bag(bag_dir: str) -> tuple:
    """Trail, per-scan (endpoints, free points), last /map, latest scan in map."""
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=bag_dir, storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/tf", "/scan", "/map"]))
    map_odom, odom_base, have_map = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), False
    trail, scans, last_scan_pose, last_map = [], [], None, None
    latest_scan = None
    while reader.has_next():
        topic, raw, _ = reader.read_next()
        if topic == "/tf":
            frames = planar_transforms(deserialize_message(raw, TFMessage))
            map_odom = frames.get(("map", "odom"), map_odom)
            odom_base = frames.get(("odom", "base_footprint"), odom_base)
            have_map = have_map or ("map", "odom") in frames
            if have_map:
                robot = compose(map_odom, odom_base)
                if not trail or math.dist(robot[:2], trail[-1][:2]) >= TRAIL_STEP_M:
                    trail.append(robot)
            continue
        if topic == "/map":
            last_map = deserialize_message(raw, OccupancyGrid)
            continue
        if not have_map:
            continue
        robot = compose(map_odom, odom_base)
        latest_scan = (raw, robot)
        if last_scan_pose and (
            math.dist(robot[:2], last_scan_pose[:2]) < SCAN_STEP_M
            and angle_gap(robot[2], last_scan_pose[2]) < SCAN_STEP_RAD
        ):
            continue
        last_scan_pose = robot
        scan = deserialize_message(raw, LaserScan)
        scans.append(scan_points(scan, compose(robot, LASER_IN_BASE)))
    latest = {"origin": [], "points": []}
    if latest_scan:
        raw, robot = latest_scan
        laser = compose(robot, LASER_IN_BASE)
        ends, _ = scan_points(deserialize_message(raw, LaserScan), laser)
        latest = {
            "origin": [round(laser[0], 3), round(laser[1], 3)],
            "points": [[round(float(x), 3), round(float(y), 3)] for x, y in ends],
        }
    return trail, scans, last_map, latest


def build_grid(scans: list) -> tuple:
    ends = np.concatenate([e for e, _ in scans])
    along = np.concatenate([a for _, a in scans])
    origin = ends.min(axis=0) - 0.5
    width, height = (np.ceil((ends.max(axis=0) + 0.5 - origin) / RESOLUTION_M)).astype(
        int
    )

    def counts(points: np.ndarray) -> np.ndarray:
        cols = ((points[:, 0] - origin[0]) / RESOLUTION_M).astype(int)
        rows = ((points[:, 1] - origin[1]) / RESOLUTION_M).astype(int)
        inside = (cols >= 0) & (cols < width) & (rows >= 0) & (rows < height)
        flat = rows[inside] * width + cols[inside]
        return np.bincount(flat, minlength=width * height).reshape(height, width)

    hits, passes = counts(ends), counts(along)
    grid = np.full((height, width), UNKNOWN, dtype=np.uint8)
    grid[passes > 0] = FREE
    wall = (hits >= MIN_WALL_HITS) & (hits > WALL_HIT_RATIO * (hits + passes))
    grid[wall] = WALL
    # rows bottom (min y) first here; flip so row 0 is the top, as in a .pgm
    return np.flipud(grid), origin


def bag_end_s(bag_dir: str) -> float:
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=bag_dir, storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    metadata = reader.get_metadata()
    end = metadata.starting_time + metadata.duration
    return end.nanoseconds / 1e9


def grid_from_map(occupancy: OccupancyGrid) -> tuple:
    info = occupancy.info
    values = np.array(occupancy.data, dtype=np.int16).reshape(info.height, info.width)
    grid = np.full(values.shape, UNKNOWN, dtype=np.uint8)
    grid[(values >= 0) & (values < FREE_BELOW)] = FREE
    grid[values > WALL_ABOVE] = WALL
    origin = np.array([info.origin.position.x, info.origin.position.y])
    return np.flipud(grid), origin, float(info.resolution)


def remove_wall_specks(grid: np.ndarray) -> int:
    """Turn wall blobs smaller than MIN_WALL_BLOB (8-connected) into free."""
    seen = np.zeros(grid.shape, dtype=bool)
    removed = 0
    height, width = grid.shape
    for row, col in zip(*np.nonzero(grid == WALL), strict=True):
        if seen[row, col]:
            continue
        blob, queue = [], deque([(row, col)])
        seen[row, col] = True
        while queue:
            r, c = queue.popleft()
            blob.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < height
                        and 0 <= nc < width
                        and not seen[nr, nc]
                        and grid[nr, nc] == WALL
                    ):
                        seen[nr, nc] = True
                        queue.append((nr, nc))
        if len(blob) < MIN_WALL_BLOB:
            for r, c in blob:
                grid[r, c] = FREE
            removed += len(blob)
    return removed


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


def build_targets(saved: dict, profiles: dict, now_s: float) -> list:
    """Targets as the page shows them, aged against `now_s` (the bag's end)."""
    targets = []
    for target in saved["targets"]:
        profile = profiles.get(target["label"], {})
        abbrev = profile.get("abbrev", target["label"].upper()[:2])
        age_s = max(0.0, now_s - target["last_seen_s"])
        targets.append(
            {
                "id": str(target["target_id"]),
                "label": target["label"],
                "display_name": profile.get("display_name", target["label"]),
                "badge": f"{abbrev}{target['target_id']}",
                "x": round(target["xyz_world"][0], 3),
                "y": round(target["xyz_world"][1], 3),
                "observation_count": target["observation_count"],
                "seen_ago_s": round(age_s, 1),
                "is_lost": age_s > LOST_AFTER_S,
            }
        )
    return targets


def main() -> None:
    map_name, bag_dir = sys.argv[1], sys.argv[2]
    targets_name = sys.argv[3] if len(sys.argv) > 3 else map_name
    trail, scans, last_map, latest_scan = read_bag(bag_dir)
    if last_map is not None:
        grid, origin, resolution = grid_from_map(last_map)
    else:
        grid, origin = build_grid(scans)
        resolution = RESOLUTION_M
    specks = remove_wall_specks(grid)
    fill_single_holes(grid)
    profiles = {
        p["canonical_class"]: p
        for p in yaml.safe_load(PROFILES.read_text())["class_profiles"]
    }
    saved_path = SEMANTIC_DIR / f"{targets_name}.json"
    saved = json.loads(saved_path.read_text()) if saved_path.exists() else None
    height, width = grid.shape
    rows, cols = np.nonzero(grid == WALL)
    wall_points = np.column_stack(
        (
            origin[0] + (cols + 0.5) * resolution,
            origin[1] + (height - 1 - rows + 0.5) * resolution,
        )
    )
    walls, clutter = fit_walls(wall_points, resolution)
    data = {
        "map_name": map_name,
        "resolution": round(resolution, 4),
        "origin": [round(float(v), 3) for v in origin],
        "width": int(width),
        "height": int(height),
        # rows top (max y) to bottom, as in a .pgm; one char per cell
        "cells": "".join("".join(map(str, row)) for row in grid),
        "walls": walls,
        "clutter": [[round(float(x), 3), round(float(y), 3)] for x, y in clutter],
        "targets": build_targets(saved, profiles, bag_end_s(bag_dir)) if saved else [],
        "scan": latest_scan,
        "run": run_series(bag_dir, saved, BATTERY_SAMPLE_LOG),
        "trail": [[round(x, 3), round(y, 3), round(th, 3)] for x, y, th in trail],
    }
    OUT.write_text(
        "// Generated by make_mockup_data.py; real data from run "
        f"{map_name}.\nwindow.MOCKUP_DATA = {json.dumps(data)};\n"
    )
    source = "/map" if last_map is not None else f"{len(scans)} scans"
    print(
        f"{OUT}: {width}x{height} cells from {source}, {specks} speck cells "
        f"removed, {len(walls)} wall segments, {len(clutter)} clutter cells, "
        f"{len(data['targets'])} targets, {len(trail)} trail points"
    )


if __name__ == "__main__":
    main()
