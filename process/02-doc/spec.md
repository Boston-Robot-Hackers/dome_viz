# dome_viz — Spec

## What it is

A **friendly, read-only view of the DOME robot's map as it is built**, for
people watching the robot work, not for debugging. It shows:

- the **floor plan** SLAM is building,
- the **objects** the robot has found (`dome_semantic`'s confirmed targets),
- **where the robot is**, and where it has been,
- **what the camera sees**, on request.

Everything is **cleaned up and less detailed than the raw topics** RViz shows.

## Where it runs

- **On a laptop connected to the robot, never on the robot's Pi.** The Pi has
  no CPU to spare, so all rendering and serving happens on the laptop.
- The laptop reaches the robot over the same Wi-Fi ROS 2 (DDS) link RViz
  already uses. The Pi only publishes topics it already publishes.

## Architecture

- **A bridge node on the laptop** subscribes to the robot's topics and pushes
  a simplified state to the browser over a local websocket.
- **A web page served on `localhost`**, opened in the laptop's browser. Its
  HTML, CSS and JS live in their own files.
- **Read-only**: it never publishes anything to the robot.
- **Topic-driven**, so it works the same against the live robot and against
  `ros2 bag play` of a recorded run.

## Inputs

| Topic | Type | From |
|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | slam_toolbox (`dome_nav`) |
| `/semantic/targets` | `dome_semantic_msgs/SemanticTargetArray` | `dome_semantic` |
| `/tf`, `/tf_static` (`map → base_footprint`) | `tf2_msgs/TFMessage` | SLAM + `dome2` |
| `/oak/image_annotated_compressed` | `sensor_msgs/CompressedImage` | `dome_vision` (only while the camera panel is open) |

Display names and abbrevs for objects come from `dome_semantic`'s
`config/class_profiles.yaml`.

## Dependencies

- `dome_semantic_msgs` and `dome_semantic` (for its class profiles) on the
  laptop. No robot package depends on `dome_viz`.
