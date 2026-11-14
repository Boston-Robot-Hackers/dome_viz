#!/usr/bin/env python3
# run_history — the robot's trail and the run's graph series, sent as deltas
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license
"""Point histories that grow over a run and reach the page in pieces.

A `History` is capped (oldest dropped) and thinned (a point too close to the
last one is skipped). It counts the points not yet broadcast, so a page that
opens mid-run gets a snapshot of what the others already have, and then the
same deltas as everyone else, with no point sent to it twice.

**The trail is stored in `odom`**, which never jumps. Each send converts it
through the current `map -> odom`. When slam_toolbox corrects that transform
by more than a little, the whole trail is resent, so it moves with the map
instead of cutting through walls.

The page drops its own oldest points past `max_points`, as the server does.
"""

import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

TRAIL_STEP_M = 0.05
TRAIL_MAX_POINTS = 2000
TRAIL_RESEND_M = 0.05  # a map -> odom correction bigger than this resends
TRAIL_RESEND_RAD = 0.02
SERIES_STEP_S = 2.0
SERIES_MAX_POINTS = 1800  # one hour at one point per 2 s
SERIES_NAMES = ("battery_pct", "power_w", "speed_mps", "objects")


@dataclass(frozen=True)
class Pose2D:
    x_m: float
    y_m: float
    yaw_rad: float


def compose(parent: Pose2D, child: Pose2D) -> Pose2D:
    """`child`, given in `parent`'s frame, expressed in the frame above it."""
    cos, sin = math.cos(parent.yaw_rad), math.sin(parent.yaw_rad)
    return Pose2D(
        parent.x_m + cos * child.x_m - sin * child.y_m,
        parent.y_m + sin * child.x_m + cos * child.y_m,
        parent.yaw_rad + child.yaw_rad,
    )


def has_shifted(old: Pose2D, new: Pose2D) -> bool:
    yaw_change = abs(math.remainder(new.yaw_rad - old.yaw_rad, math.tau))
    moved_m = math.hypot(new.x_m - old.x_m, new.y_m - old.y_m)
    return moved_m > TRAIL_RESEND_M or yaw_change > TRAIL_RESEND_RAD


def distance_step(previous: tuple, new: tuple) -> float:
    return math.dist(previous, new)


def time_step(previous: tuple, new: tuple) -> float:
    return new[0] - previous[0]


class History:
    """Capped points, thinned to `min_step` apart as measured by `step`."""

    def __init__(self, max_points: int, min_step: float, step: Callable):
        self.points: deque = deque(maxlen=max_points)
        self.min_step = min_step
        self.step = step
        self.unsent_count = 0

    def add(self, point: tuple) -> None:
        if self.points and self.step(self.points[-1], point) < self.min_step:
            return
        self.points.append(point)
        self.unsent_count = min(self.unsent_count + 1, len(self.points))

    def sent(self) -> list:
        """The points already broadcast: a new page's starting snapshot."""
        return list(self.points)[: len(self.points) - self.unsent_count]

    def take_unsent(self) -> list:
        new = list(self.points)[len(self.points) - self.unsent_count :]
        self.unsent_count = 0
        return new


class Trail:
    """The robot's path this run, kept in `odom`, sent in `map`."""

    def __init__(self):
        self.history = History(TRAIL_MAX_POINTS, TRAIL_STEP_M, distance_step)
        self.sent_map_from_odom: Pose2D | None = None

    def add(self, robot_in_odom: Pose2D, map_from_odom: Pose2D) -> dict | None:
        """Record a pose; return the message to broadcast, if any."""
        self.history.add((robot_in_odom.x_m, robot_in_odom.y_m))
        sent = self.sent_map_from_odom
        if sent is None or has_shifted(sent, map_from_odom):
            self.history.take_unsent()
            self.sent_map_from_odom = map_from_odom
            return self.message(list(self.history.points), is_full=True)
        new = self.history.take_unsent()
        return self.message(new, is_full=False) if new else None

    def snapshot(self) -> dict:
        return self.message(self.history.sent(), is_full=True)

    def message(self, odom_points: list, is_full: bool) -> dict:
        transform = self.sent_map_from_odom
        map_points = []
        if transform is not None:
            for x_m, y_m in odom_points:
                pose = compose(transform, Pose2D(x_m, y_m, 0.0))
                map_points.append([round(pose.x_m, 3), round(pose.y_m, 3)])
        return {
            "type": "trail",
            "is_full": is_full,
            "max_points": TRAIL_MAX_POINTS,
            "points": map_points,
        }


class RunSeries:
    """The run's graphs: [seconds since run start, value] per series."""

    def __init__(self, start_s: float):
        self.start_s = start_s
        self.series = {
            name: History(SERIES_MAX_POINTS, SERIES_STEP_S, time_step)
            for name in SERIES_NAMES
        }

    def add(self, values: dict, now_s: float) -> dict | None:
        """Record `{series name: value}`; return the delta to broadcast, if any."""
        run_s = round(now_s - self.start_s, 1)
        for name, value in values.items():
            self.series[name].add((run_s, round(float(value), 2)))
        new = {name: self.series[name].take_unsent() for name in values}
        new = {name: points for name, points in new.items() if points}
        return self.message(new, is_full=False) if new else None

    def snapshot(self) -> dict:
        sent = {name: history.sent() for name, history in self.series.items()}
        return self.message(sent, is_full=True)

    def message(self, series_points: dict, is_full: bool) -> dict:
        return {
            "type": "run",
            "is_full": is_full,
            "max_points": SERIES_MAX_POINTS,
            "series": {
                name: [list(point) for point in points]
                for name, points in series_points.items()
            },
        }
