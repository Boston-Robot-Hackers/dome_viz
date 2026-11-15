#!/usr/bin/env python3
# view_state — robot data in, the page's JSON messages out
# Author: Pito Salas and Claude Code
# Version: 4
# Created: 2026-11-14
# Updated: 2026-11-15
# Open Source Under MIT license
"""Everything the page shows, kept as plain state and sent as JSON messages.

The bridge calls one `on_*` method per incoming message, with the current
time, and broadcasts what it returns. It calls `tick` about once a second
(status, and targets whose "lost" flag and age change with time alone), and
`snapshot` for a page that has just connected. Not thread-safe: the bridge
holds a lock around every call.

**Run start is a quiet gap.** The first robot message ever, or the first one
after every source has been silent for over RUN_GAP_S, starts a new run: a
fresh floor planner, trail and graph series, and the run ticker restarts.

Messages, by `type`:

- `floor_plan`: `floor` is the grid as base64 bytes (row-major, row 0 at the
  lowest y; 0 unknown, 1 free), plus wall segments and clutter in `map` metres.
- `targets`, `robot`, `laser`: positions in `map` metres. A target also
  carries its raw `label` — the detector's class, e.g. "can", *not* the
  profile's canonical "soda can" — which the page needs to choose that
  object's icon and colour.
- `trail`, `run`: see `run_history`.
- `status`: seconds since each source was heard (None if never), the run's
  elapsed seconds, and one `state`: live, waiting_for_map or not_connected.
"""

import base64
import math
from collections.abc import Sequence
from dataclasses import dataclass

from dome_viz.floor_plan import FloorPlan, FloorPlanner, OccupancyData
from dome_viz.run_history import Pose2D, RunSeries, Trail, compose

LOST_TIMEOUT_S = 5.0  # dome_semantic's lost_timeout_s default
QUIET_S = 5.0  # all sources quieter than this: robot not connected
RUN_GAP_S = 30.0
LASER_PERIOD_S = 0.2
LASER_RAY_STRIDE = 3
SOURCES = ("map", "targets", "pose", "laser", "camera", "battery", "odom")


@dataclass(frozen=True)
class TargetData:
    """One `SemanticTarget`: `label` is the detector's class, e.g. "can".

    Not the profile's `canonical_class` ("soda can") — assuming otherwise is
    what made the label lookup silently miss every time.
    """

    target_id: str
    label: str
    x_m: float
    y_m: float
    observation_count: int
    last_seen_s: float


@dataclass(frozen=True)
class ScanData:
    """One `LaserScan`, in the lidar's own frame."""

    angle_min_rad: float
    angle_increment_rad: float
    range_min_m: float
    range_max_m: float
    ranges_m: Sequence


def name_and_id(label: str, target_id: str, profiles: dict) -> tuple:
    """("soda can", "CN1"), as dome_semantic labels the camera image.

    `profiles` must be keyed by the **detector label** the robot publishes
    ("can"), not by `canonical_class` ("soda can") — the bridge joins the two
    through each profile's `detector_labels`.

    A profile's name is its `display_name`, or its `canonical_class` when it
    has none, since the canonical class is already the readable form. With no
    profile at all: the raw label, and its first two letters as the prefix.
    """
    profile = profiles.get(label)
    name = (profile.display_name or profile.canonical_class) if profile else label
    prefix = profile.abbrev if profile and profile.abbrev else label[:2].upper()
    return name, f"{prefix}{target_id}"


def target_entry(target: TargetData, profiles: dict, now_s: float) -> dict:
    name, short_id = name_and_id(target.label, target.target_id, profiles)
    seen_ago_s = now_s - target.last_seen_s
    return {
        "id": short_id,
        "name": name,
        "label": target.label,
        "x": round(target.x_m, 3),
        "y": round(target.y_m, 3),
        "observations": target.observation_count,
        "is_lost": seen_ago_s > LOST_TIMEOUT_S,
        "seen_ago_s": round(seen_ago_s, 1),
    }


def laser_hits(lidar_in_map: Pose2D, scan: ScanData) -> list:
    """Every LASER_RAY_STRIDE-th valid range as a hit point in `map` metres."""
    hits = []
    for index in range(0, len(scan.ranges_m), LASER_RAY_STRIDE):
        range_m = scan.ranges_m[index]
        if not scan.range_min_m <= range_m <= scan.range_max_m:
            continue
        angle = scan.angle_min_rad + index * scan.angle_increment_rad
        ray_end = Pose2D(range_m * math.cos(angle), range_m * math.sin(angle), 0.0)
        hit = compose(lidar_in_map, ray_end)
        hits.append([round(hit.x_m, 3), round(hit.y_m, 3)])
    return hits


def floor_plan_message(plan: FloorPlan) -> dict:
    height, width = plan.floor.shape
    return {
        "type": "floor_plan",
        "width": width,
        "height": height,
        "resolution_m": plan.resolution_m,
        "origin": [round(value, 3) for value in plan.origin_xy_m],
        "floor": base64.b64encode(plan.floor.tobytes()).decode("ascii"),
        "walls": plan.walls,
        "clutter": plan.clutter_xy_m.round(3).tolist(),
    }


class ViewState:
    """The page's state for one viewer process; see the module docstring."""

    def __init__(self, profiles: dict):
        self.profiles = profiles
        self.heard_s: dict = {}
        self.planner = FloorPlanner()
        self.trail = Trail()
        self.run: RunSeries | None = None
        self.floor_plan: dict | None = None
        self.targets: list = []
        self.robot: dict | None = None
        self.laser_sent_s: float | None = None

    def heard(self, source: str, now_s: float) -> list:
        """Note a message from `source`; start a new run after a quiet gap."""
        last_s = max(self.heard_s.values(), default=None)
        self.heard_s[source] = now_s
        if last_s is not None and now_s - last_s <= RUN_GAP_S:
            return []
        self.planner, self.trail, self.run = FloorPlanner(), Trail(), RunSeries(now_s)
        return [self.trail.snapshot(), self.run.snapshot()]

    def on_map(self, occupancy: OccupancyData, now_s: float) -> list:
        messages = self.heard("map", now_s)
        self.floor_plan = floor_plan_message(self.planner.update(occupancy))
        return [*messages, self.floor_plan]

    def on_targets(self, targets: list, now_s: float) -> list:
        messages = self.heard("targets", now_s)
        self.targets = targets
        messages.append(self.targets_message(now_s))
        series = self.run.add({"objects": len(targets)}, now_s)
        return messages + ([series] if series else [])

    def on_pose(
        self, robot_in_odom: Pose2D, map_from_odom: Pose2D, now_s: float
    ) -> list:
        messages = self.heard("pose", now_s)
        robot = compose(map_from_odom, robot_in_odom)
        self.robot = {
            "type": "robot",
            "x": round(robot.x_m, 3),
            "y": round(robot.y_m, 3),
            "yaw": round(math.remainder(robot.yaw_rad, math.tau), 3),
        }
        messages.append(self.robot)
        trail = self.trail.add(robot_in_odom, map_from_odom)
        return messages + ([trail] if trail else [])

    def on_scan(self, lidar_in_map: Pose2D, scan: ScanData, now_s: float) -> list:
        messages = self.heard("laser", now_s)
        last_s = self.laser_sent_s
        if last_s is not None and now_s - last_s < LASER_PERIOD_S:
            return messages
        self.laser_sent_s = now_s
        origin = [round(lidar_in_map.x_m, 3), round(lidar_in_map.y_m, 3)]
        hits = laser_hits(lidar_in_map, scan)
        return [*messages, {"type": "laser", "origin": origin, "hits": hits}]

    def on_battery(self, percent: float, power_w: float, now_s: float) -> list:
        messages = self.heard("battery", now_s)
        series = self.run.add({"battery_pct": percent, "power_w": power_w}, now_s)
        return messages + ([series] if series else [])

    def on_speed(self, speed_mps: float, now_s: float) -> list:
        messages = self.heard("odom", now_s)
        series = self.run.add({"speed_mps": speed_mps}, now_s)
        return messages + ([series] if series else [])

    def on_camera(self, now_s: float) -> list:
        """Only noted for status; the bridge passes the JPEG through itself."""
        return self.heard("camera", now_s)

    def targets_message(self, now_s: float) -> dict:
        entries = [
            target_entry(target, self.profiles, now_s) for target in self.targets
        ]
        return {"type": "targets", "targets": entries}

    def status_message(self, now_s: float) -> dict:
        ages = {
            source: round(now_s - self.heard_s[source], 1)
            if source in self.heard_s
            else None
            for source in SOURCES
        }
        is_connected = any(age is not None and age <= QUIET_S for age in ages.values())
        if not is_connected:
            state = "not_connected"
        elif "map" not in self.heard_s:
            state = "waiting_for_map"
        else:
            state = "live"
        run_s = None if self.run is None else round(now_s - self.run.start_s, 1)
        return {"type": "status", "state": state, "ages_s": ages, "run_s": run_s}

    def tick(self, now_s: float) -> list:
        return [self.status_message(now_s), self.targets_message(now_s)]

    def snapshot(self, now_s: float) -> list:
        """Everything a newly connected page needs, before the next deltas."""
        known = [self.floor_plan, self.robot]
        messages = [message for message in known if message is not None]
        messages += [self.targets_message(now_s), self.trail.snapshot()]
        if self.run is not None:
            messages.append(self.run.snapshot())
        return [*messages, self.status_message(now_s)]
