# TF01 Live map view, for Feature F01

For each task step, add a test when feasible. If not feasible, note why.

**Shape**: pure modules (`floor_plan.py`, `view_state.py`) with no ROS
imports; a ROS adapter (`bridge_node.py`); a local web server
(`web_server.py`); and the page (`static/index.html`, `app.css`, `app.js`).
The bridge turns topics into small JSON messages; the browser does all the
drawing.

## TF01.0 — Decide the web stack

**Status**: done 2026-11-13 — `aiohttp` (apt) for HTTP + websocket in
its own asyncio thread; plain JS + canvas in the browser. Why: `notes.md`,
"Web stack".

**Description**: Pick the websocket/HTTP server library (e.g. `websockets`
or `aiohttp`) and how it runs beside `rclpy`'s executor (its own thread with
an asyncio loop). Pick the browser side: plain JS with an HTML canvas, or a
small pan/zoom library loaded from a local file. The TF01.1 mockup uses
the same choice. **Prefer what's installable
on the viewer VM (Ubuntu) with `apt` (`python3-…`)** and the fewest moving parts. Record
the choice and why in `process/02-doc/notes.md`.

*Test*: none. It's a decision.

## TF01.1 — Layout mockup

**Status**: done 2026-11-13 — approved by the user. Agreed layout in
`process/02-doc/layout.md`; mockup in `mockup/` (data from the `viz01` drive:
its last `/map`, real trail and scan, targets from the `viz01replay` bag
replay). Changes from the plan: walls are **fitted straight segments**
(`mockup/wall_lines.py`), not cleaned cells; a **coordinate grid** with a
marked 0, 0; a **laser overlay** (`/scan`, rays and hits); the robot drawn
from the URDF. No screenshot (built on the robot, no browser); the mockup is
the reference. Theme left at follow-the-system.

**Description**: A static, clickable mockup of the page, before any page
code: the real floor plan from `f36run6.pgm`, the real targets from that run
(`~/.dome/semantic_maps/f36run6.json`), a fake robot pose and trail, and a
placeholder camera image. No ROS, no server. It uses TF01.0's browser
approach, so the approved mockup becomes TF01.7's starting point.

It settles:

- **Arrangement**: full-screen map with floating panels, or map plus a
  sidebar listing the objects.
- **Camera**: corner picture-in-picture, side panel, or its own tab.
- **Object badges**: icon, name and ID; how "lost" looks; what a click does
  (details, centre the map).
- **Status**: banner, connection light, or per-source list.
- **Look**: palette, light or dark.

Iterate with the user until approved. Save the agreed layout (short
description plus a screenshot) in `process/02-doc/layout.md`, and adjust
TF01.4's messages if the layout needs fields they don't carry.

*Test*: the user's approval of the mockup. Not automatable.

## TF01.2 — Package skeleton

**Status**: not done

**Description**: `ament_python` package: `package.xml` (`rclpy`,
`nav_msgs`, `sensor_msgs`, `tf2_ros`, `dome_semantic_msgs`, `dome_semantic`,
the TF01.0 library), `setup.py` installing `static/` and `launch/` into
`share/`, one entry point for the bridge, `test/`. Update `CLAUDE.md`'s
Commands if TF01.0 changes them.

*Test*: `colcon build --packages-select dome_viz` succeeds and an import
test loads each module.

## TF01.3 — Floor plan cleanup (pure)

**Status**: not done

**Description**: `floor_plan.py`: `OccupancyGrid` data (width, height,
resolution, origin, cells) → a compact grid of three classes, wall / free /
unknown. Threshold occupancy, then **remove isolated wall specks** (small
connected blobs) and fill single-cell holes. Then **fit straight wall
segments** (start from `mockup/wall_lines.py`): the room's main direction,
greedy lines along it, corners closed, doorways (gaps over 0.3 m) kept open;
leftover wall cells are clutter. **Keep walls steady between map updates**:
hold the main direction once found, and keep segment ends unless the map
under them changed. numpy only. Output: the floor (free/unknown) grid, wall
segments and clutter cells in `map` metres, plus the map's origin and
resolution.

*Test*: synthetic grids (a speck is removed, a wall line survives, unknown
stays unknown), plus a real map loaded from a saved `.pgm` copied into
`test/fixtures/` (e.g. `f36run6.pgm` + `.yaml`): the cleaned map keeps its
walls and has fewer isolated wall cells. Walls: an L of wall cells gives
two segments meeting at a corner; a gap over 0.3 m splits a wall; a rotated
room's segments come out at its angle; refitting an unchanged map gives the
same segments.

## TF01.4 — View state (pure)

**Status**: not done

**Description**: `view_state.py` builds the JSON messages the page gets:

- **Targets**: for each `SemanticTarget`, its map position, `display_name`
  and `abbrev` + ID (from `dome_semantic`'s class profiles, e.g.
  "soda can · CN1"), observation count, and **`is_lost`**. The message has
  no lost flag, so a target is lost when `last_seen` is older than a
  threshold (default 5 s, `dome_semantic`'s `lost_timeout_s`).
- **Robot**: position and heading in `map`.
- **Floor plan**: floor grid, wall segments and clutter from `floor_plan.py`,
  sent only when `/map` changes.
- **Laser**: the latest `/scan` as the lidar's position plus its hit points
  in `map` (through the `laser` frame's TF at the scan's stamp), so the page
  can draw rays. Downsampled, at most ~5 Hz.
- **Trail**: append a point only when the robot has moved more than a few
  cm; cap its length.
- **Status**: per source (map, targets, pose, laser, camera), seconds since
  the last message, plus the one overall state the page shows as a sentence:
  live, waiting for the map, or robot not connected (all robot sources
  quiet for more than a few seconds).
- **Targets** also carry **seconds since last seen**, for the list's "2 min
  ago".

*Test*: label with no profile falls back to the raw label; lost threshold
at ±1 ms; trail skips sub-threshold moves and drops the oldest past the
cap; status reports a source never heard from.

## TF01.5 — Local web server

**Status**: not done

**Description**: `web_server.py` serves `static/` and one websocket on
the local network: `host` (default `0.0.0.0`, all interfaces) and `port`
are parameters. It broadcasts state messages to every open page and
receives one kind of message from the page: camera on/off. Runs in its own
thread with its own event loop; starts and stops cleanly with the node.

*Test*: start on a free port in the test, fetch `index.html`, open a
websocket, receive a broadcast, and send a camera toggle that reaches a
callback. Check it binds to the `host` it is given, and that two pages
both get the broadcast.

## TF01.6 — Bridge node

**Status**: not done

**Description**: `bridge_node.py` (ROS adapter):

- `/map` with slam_toolbox's QoS (reliable, transient local), so a page
  opened late still gets the current map.
- `/scan` (sensor-data QoS), for the laser overlay.
- `/semantic/targets`, and the robot pose from TF `map → base_footprint`
  on a timer (~10 Hz).
- **Camera**: subscribes to `/oak/image_annotated_compressed` only while
  at least one page has the camera on, and destroys the subscription when
  none does, so a closed panel costs the Pi nothing. JPEG bytes go to the
  page as-is.
- Honors `use_sim_time` for bag replay. Rate-limits pushes so a fast topic
  can't flood the browser.

*Test*: callbacks fed fake messages produce the expected pushes, with the
graph mocked. The camera subscription exists only between a "camera on"
and the last "camera off". A pose push is skipped when TF has no transform.

## TF01.7 — Page: floor plan, robot, pan and zoom

**Status**: not done

**Description**: `index.html` + `app.css` + `app.js`: draw the floor plan
on a canvas in a clean palette (walls dark, free light, unknown as page
background), the robot as an icon with heading, and the trail as a soft
line. Pan with drag, zoom with wheel or pinch, a "follow robot" toggle, and
a scale bar in metres. Redraw only what changed.

*Test*: manual, in a browser against bag replay; record the steps and
result in `current.md`. A JS test toolchain isn't worth adding for this.

## TF01.8 — Page: objects, camera, status

**Status**: not done

**Description**: Draw each target as a badge with its icon, display name and
ID, readable at any zoom; lost targets faded, not hidden. A camera
picture-in-picture panel, off by default, whose toggle sends camera on/off.
A status line that says plainly when a source has gone quiet ("No map yet",
"Robot not connected").

*Test*: manual, as TF01.7.

## TF01.9 — Launch and make target

**Status**: not done

**Description**: `launch/view.launch.py` starts the bridge (args:
`use_sim_time`, `host`, `port`) and prints the page URLs: `localhost` and
the VM's network address. A `make view` target in the
Makefile runs it.

*Test*: a launch-function test with a fake launcher checks the args reach
the node.

## TF01.10 — A replay bag with the map and camera

**Status**: not done

**Description**: On the robot, record a short drive with `/map` and
`/oak/image_annotated_compressed` added to the usual topics
(`dome_semantic`'s `notes.md`, "Bag replay of a drive"). Copy it to the
viewer VM. Write the record and replay commands in `notes.md`.

*Test*: manual; needs the robot. `ros2 bag info` shows both topics.

## TF01.11 — Test suite

**Status**: not done

**Description**: Make sure TF01.2–TF01.6 and TF01.9's tests exist and pass,
plus one end-to-end test: fake `/map`, target and TF messages in, the
websocket client sees a floor plan, a labelled target and a robot pose.
`ruff` clean on new files.

*Test*: this step is the tests.

## TF01.12 — Demo on the viewer VM

**Status**: not done

**Description**: The VM already sees the robot over DDS (RViz runs there), so just
confirm `ros2 topic list` shows `/map` and `/semantic/targets`. Run F01's
How to Demo against TF01.10's bag, then live against the robot, with pages
open in the VM's browser and on the Mac. **Measure the Pi's CPU** (`top`, ~60 s) with no viewer,
with the viewer and camera off, and with the camera on. Record all three in
`current.md`.

*Test*: manual. Pass: the view works on the bag and live, in both
browsers, and the Pi's CPU with the
camera off matches no viewer within noise.
