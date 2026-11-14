#!/usr/bin/env python3
# bridge_node — ROS adapter that feeds the dome_viz web page
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license
"""ROS 2 node that turns the robot's topics into messages for the web page.

Skeleton only: the subscriptions, TF lookups and web server arrive in TF01.6.
"""

import rclpy
from rclpy.node import Node


class BridgeNode(Node):
    def __init__(self):
        super().__init__("dome_viz_bridge")


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
