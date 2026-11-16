#!/usr/bin/env python3
# bridge_node — ROS adapter that feeds the dome_viz web page
# Author: Pito Salas and Claude Code
# Version: 5
# Created: 2026-11-14
# Updated: 2026-11-16
# Open Source Under MIT license
"""ROS 2 node that turns the robot's topics into messages for the web page.

One `ViewState` holds everything the page shows and this node is its only
adapter. Subscriptions and timers run on `rclpy`'s executor while the web
server runs on its own thread, so **every `ViewState` call is made under
`self.lock`** — including `on_connect`, which the server calls from its own
thread the moment a page opens.

- `/map` uses slam_toolbox's QoS (reliable, transient local), so a page
  opened late still receives the current map.
- The robot pose is a TF lookup on a timer rather than a topic:
  `odom -> ROBOT_FRAME` for the trail, which is kept in `odom`, and
  `map -> odom` to place it. A lookup that fails, **or that answers only with
  a transform older than TF_STALE_S**, is skipped rather than guessed at — see
  `lookup`.
- **A scan waits for its transform.** `/scan` is stamped ~45 ms ahead of
  the newest `map -> laser` transform, so looking it up at its own stamp at
  once almost always extrapolates. The newest scan is held in `pending_scan`
  and retried on the pose timer until TF reaches its stamp; a newer scan
  replaces it. A blocking wait cannot work: the TF listener shares this
  single-threaded executor.
- **The camera costs the Pi nothing while nobody watches it.** The
  subscription exists only while some page has the panel on. The server's
  callback merely records the wish; `reconcile_camera` on the pose timer
  creates and destroys the subscription, so that work happens on the
  executor's thread rather than the server's.
- Pushes are rate-limited inside `ViewState` already (the laser to ~5 Hz, the
  run graphs to ~1 point per 2 s) and it returns nothing when there is
  nothing new, so a fast topic cannot flood the browser.
"""

import math
import threading
from pathlib import Path

import rclpy
from ament_index_python.packages import (
    PackageNotFoundError,
    get_package_share_directory,
)
from dome_semantic.class_profiles import build_label_map, load_class_profiles
from dome_semantic_msgs.msg import SemanticTargetArray
from dome_telemetry_msgs.msg import BatteryStats
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
    qos_profile_sensor_data,
)
from rclpy.time import Time
from sensor_msgs.msg import CompressedImage, LaserScan
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

from dome_viz.floor_plan import OccupancyData
from dome_viz.run_history import Pose2D
from dome_viz.view_state import ScanData, TargetData, ViewState
from dome_viz.web_server import ServerConfig, WebServer

MAP_FRAME = "map"
ODOM_FRAME = "odom"
ROBOT_FRAME = "base_footprint"
CAMERA_TOPIC = "/oak/image_annotated_compressed"
POSE_PERIOD_S = 0.1
TICK_PERIOD_S = 1.0
# Generous against slam_toolbox's 20 Hz map -> odom (dome_nav's
# transform_publish_period is 0.05 s), tight enough that a gone robot stops
# being drawn well before QUIET_S makes the page say so.
TF_STALE_S = 2.0

MAP_QOS = QoSProfile(
    depth=1,
    reliability=QoSReliabilityPolicy.RELIABLE,
    durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
)

# The robot's own vision config is the authority on class names and
# abbreviations, so the viewer reads the same file rather than keeping a copy
# that would drift from what the camera image is labelled with.
PROFILE_PACKAGE = "dome_vision_ros"
PROFILE_RELATIVE = "config/class_profiles.yaml"


def default_profile_path() -> str:
    """The installed class profiles, or "" when that package is not here.

    Labels are optional: with no profiles a target still shows its raw label,
    which is `name_and_id`'s designed fallback, so a viewer on a machine
    without the vision package keeps working.
    """
    try:
        share = get_package_share_directory(PROFILE_PACKAGE)
    except PackageNotFoundError:
        return ""
    path = Path(share) / PROFILE_RELATIVE
    return str(path) if path.is_file() else ""


def yaw_of(quaternion) -> float:
    """The yaw of a `geometry_msgs/Quaternion`, in radians."""
    along = 2.0 * (quaternion.w * quaternion.z + quaternion.x * quaternion.y)
    across = 1.0 - 2.0 * (quaternion.y**2 + quaternion.z**2)
    return math.atan2(along, across)


def pose2d_of(transform) -> Pose2D:
    """A `geometry_msgs/Transform` flattened to the floor."""
    return Pose2D(
        transform.translation.x, transform.translation.y, yaw_of(transform.rotation)
    )


def stamp_s(stamp) -> float:
    return stamp.sec + stamp.nanosec * 1e-9


def occupancy_of(grid: OccupancyGrid) -> OccupancyData:
    origin = grid.info.origin.position
    return OccupancyData(
        width=grid.info.width,
        height=grid.info.height,
        resolution_m=grid.info.resolution,
        origin_xy_m=(origin.x, origin.y),
        cells=grid.data,
    )


def targets_of(array: SemanticTargetArray) -> list:
    return [
        TargetData(
            target_id=target.target_id,
            label=target.label,
            x_m=target.pose.position.x,
            y_m=target.pose.position.y,
            observation_count=target.observation_count,
            last_seen_s=stamp_s(target.last_seen),
        )
        for target in array.targets
    ]


def scan_of(scan: LaserScan) -> ScanData:
    return ScanData(
        angle_min_rad=scan.angle_min,
        angle_increment_rad=scan.angle_increment,
        range_min_m=scan.range_min,
        range_max_m=scan.range_max,
        ranges_m=scan.ranges,
    )


class BridgeNode(Node):
    """Topics in, page messages out; see the module docstring."""

    def __init__(self):
        super().__init__("dome_viz_bridge")
        host = self.declare_parameter("host", "0.0.0.0").value
        port = self.declare_parameter("port", 8080).value
        profile_path = self.declare_parameter(
            "class_profile_path", default_profile_path()
        ).value

        self.lock = threading.Lock()
        self.view = ViewState(self.profiles(profile_path))
        self.is_camera_wanted = False
        self.camera_subscription = None
        self.pending_scan: LaserScan | None = None

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        static_dir = Path(get_package_share_directory("dome_viz")) / "static"
        self.server = WebServer(
            ServerConfig(static_dir, host, port),
            self.on_connect,
            self.on_camera_change,
        )
        self.subscribe()
        self.create_timer(POSE_PERIOD_S, self.push_pose)
        self.create_timer(TICK_PERIOD_S, self.push_tick)
        self.server.start()
        self.get_logger().info(f"page at http://{host}:{port}/")

    def profiles(self, path: str) -> dict:
        """Class profiles keyed by the detector label the robot publishes.

        `load_class_profiles` keys them by `canonical_class` ("soda can"),
        while `/semantic/targets` carries the detector label ("can"), so the
        two are joined through each profile's `detector_labels`.
        """
        if not path:
            self.get_logger().warning(
                f"no class profiles found: looked for {PROFILE_PACKAGE}'s "
                f"{PROFILE_RELATIVE}; targets will show raw labels"
            )
            return {}
        by_canonical = load_class_profiles(path)
        label_map = build_label_map(by_canonical)
        return {
            label: by_canonical[canonical] for label, canonical in label_map.items()
        }

    def subscribe(self) -> None:
        self.create_subscription(OccupancyGrid, "/map", self.take_map, MAP_QOS)
        self.create_subscription(
            LaserScan, "/scan", self.take_scan, qos_profile_sensor_data
        )
        self.create_subscription(
            SemanticTargetArray, "/semantic/targets", self.take_targets, 10
        )
        self.create_subscription(
            BatteryStats, "/telemetry/battery", self.take_battery, 10
        )
        self.create_subscription(Odometry, "/odom", self.take_odom, 10)

    def now_s(self) -> float:
        """Node time, so `use_sim_time` carries through to bag replay."""
        return self.get_clock().now().nanoseconds * 1e-9

    def feed(self, method, *view_args) -> None:
        """One `ViewState` call under the lock, and its messages to the pages."""
        with self.lock:
            messages = method(*view_args, self.now_s())
        if messages:
            self.server.broadcast(messages)

    def lookup(self, parent: str, child: str, when: Time) -> Pose2D | None:
        """`child`'s pose in `parent`, or None when TF has no fresh answer.

        A `tf2` buffer only discards old transforms as new ones are inserted,
        so once a publisher stops, its last transform keeps being returned for
        ever. Anything older than TF_STALE_S is therefore treated as absent:
        a dead publisher's final transform is not where the robot is now, and
        returning it would draw a motionless robot as though it were live.
        """
        try:
            transform = self.tf_buffer.lookup_transform(parent, child, when)
        except TransformException as error:
            self.get_logger().debug(f"no transform {parent} -> {child}: {error}")
            return None
        age_s = self.now_s() - stamp_s(transform.header.stamp)
        if age_s > TF_STALE_S:
            self.get_logger().debug(f"{parent} -> {child} is {age_s:.1f} s stale")
            return None
        return pose2d_of(transform.transform)

    def take_map(self, grid: OccupancyGrid) -> None:
        self.feed(self.view.on_map, occupancy_of(grid))

    def take_targets(self, array: SemanticTargetArray) -> None:
        self.feed(self.view.on_targets, targets_of(array))

    def take_battery(self, stats: BatteryStats) -> None:
        self.feed(self.view.on_battery, stats.percent, stats.power_w)

    def take_odom(self, odometry: Odometry) -> None:
        linear = odometry.twist.twist.linear
        self.feed(self.view.on_speed, math.hypot(linear.x, linear.y))

    def take_scan(self, scan: LaserScan) -> None:
        self.pending_scan = scan
        self.resolve_scan()

    def resolve_scan(self) -> None:
        """Send the pending scan once TF can place the laser at its stamp."""
        scan = self.pending_scan
        if scan is None:
            return
        lidar_in_map = self.lookup(
            MAP_FRAME, scan.header.frame_id, Time.from_msg(scan.header.stamp)
        )
        if lidar_in_map is None:
            return
        self.pending_scan = None
        self.feed(self.view.on_scan, lidar_in_map, scan_of(scan))

    def take_camera(self, image: CompressedImage) -> None:
        self.feed(self.view.on_camera)
        self.server.send_camera(bytes(image.data))

    def push_pose(self) -> None:
        self.reconcile_camera()
        self.resolve_scan()
        latest = Time()
        robot_in_odom = self.lookup(ODOM_FRAME, ROBOT_FRAME, latest)
        map_from_odom = self.lookup(MAP_FRAME, ODOM_FRAME, latest)
        if robot_in_odom is None or map_from_odom is None:
            return
        self.feed(self.view.on_pose, robot_in_odom, map_from_odom)

    def push_tick(self) -> None:
        self.feed(self.view.tick)

    def on_connect(self) -> list:
        """A page opened; runs on the web server's thread, hence the lock."""
        with self.lock:
            return self.view.snapshot(self.now_s())

    def on_camera_change(self, is_wanted: bool) -> None:
        """Also the server's thread: only record the wish, never subscribe."""
        with self.lock:
            self.is_camera_wanted = is_wanted

    def reconcile_camera(self) -> None:
        """Match the camera subscription to what the pages want, on our thread."""
        with self.lock:
            is_wanted = self.is_camera_wanted
        if is_wanted and self.camera_subscription is None:
            self.camera_subscription = self.create_subscription(
                CompressedImage, CAMERA_TOPIC, self.take_camera, qos_profile_sensor_data
            )
            self.get_logger().info(f"a page wants the camera: {CAMERA_TOPIC} on")
        elif not is_wanted and self.camera_subscription is not None:
            self.destroy_subscription(self.camera_subscription)
            self.camera_subscription = None
            self.get_logger().info("no page wants the camera: subscription dropped")

    def destroy_node(self) -> None:
        self.server.stop()
        super().destroy_node()


def main():
    rclpy.init()
    node = BridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Ctrl-C, shutting down")
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
