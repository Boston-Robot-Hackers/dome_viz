# Notes

Semi-permanent project notes: durable architecture decisions that don't belong
in a feature or task file.

## Keep the Pi's load unchanged

**Decided 2026-11-13.** A web page served from the Pi was rejected because it
adds load to a Pi that has none to spare (`dome_vision` I02, `dome_semantic`
TF33.9). Everything runs on the viewer VM (Ubuntu in VMware on the Mac
mini), which serves the page to any browser on the local network.

**How to apply**: anything optional that costs the Pi, such as the camera
image, is subscribed only while the user is looking at it. `dome_vision` only
publishes images when someone subscribes, so an unsubscribed topic costs the Pi
nothing.

## Bags for replay need `/map` and the image

The `dome_semantic` F36 bags (e.g. `~/bags/f36run6`) record `/tf`,
`/tf_static`, `/oak/detections_3d`, `/odom`, `/scan` and `/semantic/targets`,
but **not `/map` or the camera image**. For replay, either record new bags
with `/map` and `/oak/image_annotated_compressed` added, or run `slam_toolbox`
on the VM against the bag's `/scan`.

## The viewer is a VM on the Mac mini

**Decided 2026-11-13.** `dome_viz` runs in an Ubuntu VM in VMware on the Mac
mini, not on a laptop. The VM runs the bridge and the web server; the page
opens in the VM's browser or any browser on the local network.

The VM already sees the robot's topics: it's where RViz runs.

**How to apply**: no extra network setup. If the VM ever stops seeing the
robot's topics, check VMware's networking (it must stay bridged, for DDS
discovery and so other machines can reach the page).

## `caplog` does not work in this workspace

**Found 2026-11-14 (TF01.5).** Pytest's `caplog` fixture captures nothing
here, for any logger, on any thread. It is not a `dome_viz` bug.

ROS's `launch/logging/__init__.py` calls `logging.setLoggerClass(LaunchLogger)`
(line 538), and `LaunchLogger.__init__` sets `self.propagate = False`
(line 528). The `launch_testing` and `launch_testing_ros` pytest plugins are
auto-loaded in this workspace, so that runs before collection: **every logger
created afterwards has `propagate = False`**, and no record reaches the root
logger where `caplog` installs its handler.

The giveaway is a log line appearing under *Captured stderr* with no level or
logger prefix — that is `logging.lastResort`, which fires only when a record
finds no handler at all.

**How to apply**: to assert on a log message, attach a handler directly to
that module's logger (`test_web_server.py`'s `logged_warnings` fixture is the
pattern). Never assert on `caplog.text`.

## Web stack: aiohttp and plain canvas

**Decided 2026-11-13 (TF01.0).**

- **Server: `aiohttp`** (`python3-aiohttp`, 3.9 on Ubuntu 24.04; also a
  rosdep key). One library serves both the static page and the websocket on
  one port. `websockets` (10.4 in apt) only does websockets, so static files
  would need a second server or a hack; `tornado` would work too but is
  bigger and less familiar.
- **It runs in its own thread with its own asyncio loop**, beside `rclpy`'s
  executor. ROS callbacks hand messages over with
  `asyncio.run_coroutine_threadsafe`, so neither side blocks the other.
- **Browser: plain JavaScript and an HTML `<canvas>`, no library.** Pan,
  zoom and a scale bar are a few dozen lines. No CDN (the page must work on a
  LAN with no internet), no build step, nothing to vendor.
