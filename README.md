# dome_viz

A friendly, read-only view of the DOME robot's map as it is built, running on a
laptop connected to the robot: floor plan, found objects, robot position and
trail, and the camera.

## Installation

A ROS 2 package. On the laptop, in a ROS 2 workspace:

```bash
cd ~/ros2_ws/src
git clone <repo url> dome_viz
cd ~/ros2_ws
colcon build --packages-select dome_viz
source install/setup.bash
```

## Usage

```bash
make    # list targets
```

## Development

```bash
cd ~/ros2_ws && source install/setup.bash
python3 -m pytest src/dome_viz/test
```

## License

MIT — see [LICENSE](LICENSE)
