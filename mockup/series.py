#!/usr/bin/env python3
# series — small time series for the mockup's run panel (speed, battery, objects)
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-13
# Updated: 2026-11-13
# Open Source Under MIT license
"""Build the run panel's series for the TF01.1 mockup.

Times are seconds since the run started, which is the bag's first /map (the
same start the page's run ticker counts from). Speed comes from the bag's
/odom, objects found from the saved targets' confirmation times, and battery
from a dome_telemetry daily log (the viz01 drive recorded none; see notes).
"""

import json
import math
import pathlib

import numpy as np
import rosbag2_py
from nav_msgs.msg import Odometry
from rclpy.serialization import deserialize_message

SPEED_BIN_S = 2.0


def first_map_and_odom(bag_dir: str) -> tuple:
    """(start_s, end_s, [(t_s, speed_mps)]) with start at the first /map."""
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=bag_dir, storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    reader.set_filter(rosbag2_py.StorageFilter(topics=["/map", "/odom"]))
    start_s, end_s, speeds = None, 0.0, []
    while reader.has_next():
        topic, raw, stamp_ns = reader.read_next()
        end_s = stamp_ns / 1e9
        if topic == "/map":
            start_s = end_s if start_s is None else start_s
            continue
        twist = deserialize_message(raw, Odometry).twist.twist
        speeds.append((end_s, math.hypot(twist.linear.x, twist.linear.y)))
    return start_s, end_s, speeds


def binned(samples: list, start_s: float, end_s: float, bin_s: float) -> dict:
    times = np.array([t for t, _ in samples]) - start_s
    values = np.array([v for _, v in samples])
    edges = np.arange(0.0, end_s - start_s + bin_s, bin_s)
    out_t, out_v = [], []
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        inside = (times >= low) & (times < high)
        if inside.any():
            out_t.append(round(float(low + bin_s / 2), 1))
            out_v.append(round(float(values[inside].mean()), 3))
    return {"t": out_t, "v": out_v}


def objects_found(saved: dict, start_s: float, end_s: float) -> dict:
    confirmed = sorted(t["confirmed_at_s"] - start_s for t in saved["targets"])
    times = (
        [0.0] + [round(t, 1) for t in confirmed if t >= 0] + [round(end_s - start_s, 1)]
    )
    counts = [0] + list(range(1, len(times) - 1)) + [len(times) - 2]
    return {"t": times, "v": counts, "step": True}


def battery_sample(log_path: pathlib.Path, duration_s: float) -> dict:
    """A stretch of a real daily log as long as the run, re-timed to start at 0."""
    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line]
    rows = [r for r in rows if "percent" in r]
    stamps = [r["timestamp"]["sec"] + r["timestamp"]["nanosec"] / 1e9 for r in rows]
    middle = len(rows) // 2
    first = middle
    while first > 0 and stamps[middle] - stamps[first - 1] < duration_s / 2:
        first -= 1
    picked = [
        i for i in range(first, len(rows)) if stamps[i] - stamps[first] <= duration_s
    ]
    t = [round(stamps[i] - stamps[first], 1) for i in picked]
    return {
        "source": log_path.name,
        "percent": {"t": t, "v": [round(rows[i]["percent"], 1) for i in picked]},
        "power_w": {"t": t, "v": [round(abs(rows[i]["power_w"]), 2) for i in picked]},
    }


def run_series(bag_dir: str, saved: dict | None, battery_log: pathlib.Path) -> dict:
    start_s, end_s, speeds = first_map_and_odom(bag_dir)
    duration = end_s - start_s
    return {
        "run_s": round(duration, 1),
        "speed_mps": binned(speeds, start_s, end_s, SPEED_BIN_S),
        "objects": objects_found(saved, start_s, end_s)
        if saved
        else {"t": [], "v": []},
        "battery": battery_sample(battery_log, duration),
    }
