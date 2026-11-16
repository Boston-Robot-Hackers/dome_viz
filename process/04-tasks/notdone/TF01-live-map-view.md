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
the reference. Theme left at follow-the-system. **Extended and re-approved
the same day**: a run ticker and four small graphs (battery %, power draw,
speed, objects found) with axes, full sidebar width (`mockup/series.py`).

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

**Status**: done 2026-11-14 — `colcon build` passes and `test/test_imports.py`
imports every module (2 passed). `bridge_node.py` is an empty node for now;
`static/` and `launch/` are globbed and fill in with TF01.5–TF01.7.
`ruff.toml` ignores `ERA001` (it reads the stamped header lines as code;
user's call).

**Description**: `ament_python` package: `package.xml` (`rclpy`,
`nav_msgs`, `sensor_msgs`, `tf2_ros`, `dome_semantic_msgs`, `dome_semantic`,
`dome_telemetry_msgs`,
the TF01.0 library), `setup.py` installing `static/` and `launch/` into
`share/`, one entry point for the bridge, `test/`. Update `CLAUDE.md`'s
Commands if TF01.0 changes them.

*Test*: `colcon build --packages-select dome_viz` succeeds and an import
test loads each module.

## TF01.3 — Floor plan cleanup (pure)

**Status**: done 2026-11-14 — `floor_plan.py` (classify, specks, holes,
`FloorPlanner` holding direction and unchanged walls) and `wall_fit.py`
(the line fitter, ported from `mockup/wall_lines.py`; split out to keep both
files under ~300 lines). Tests in `test_floor_plan.py` and
`test_wall_fit.py`; fixture `test/fixtures/f36run6.pgm` + `.yaml`. On
`f36run6` (sparse walls: 105 wall cells, 67 of them specks) the fit gives
one segment in 0.04 s on the Pi. `package.xml` gained `python3-numpy`
(exec) and `python3-yaml` (test, for the fixture loader). **Fixed the same
day**: the direction now locks only once there is enough wall (200 cells or
3 m fitted), not on the first map; see `chores.md`.

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

**Status**: done 2026-11-14 — `view_state.py` (`ViewState`: `on_*` per
source, `tick` ~1 Hz, `snapshot` for a new page) and `run_history.py`
(`History`, `Trail`, `RunSeries`; split out for size). Tests in
`test_view_state.py` and `test_run_history.py` (55 pass in all).

- **Labels are a copy in `dome_viz`** (user's call): `dome_semantic`'s
  `short_label` lives in a module that imports `rclpy`.
- **Deltas without per-page state**: a new page's snapshot holds only points
  already broadcast, so the next delta completes it with no duplicates.
- **Status also lists `battery` and `odom`**, since they count toward "robot
  connected" and the run gap.
- **The `run` ticker** goes out as `run_s` in each status message, not as a
  clock time, so it works under bag replay's sim time.

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
  - **Stored in `odom`**, not `map`. Each send converts the points through
    the *current* `map → odom`, so a slam_toolbox loop closure moves the
    whole trail with the map instead of leaving it cutting through walls.
  - **Held on the server**: on page load the whole trail is sent; after
    that, new points only.
  - **Cleared at run start**, together with the run ticker.
- **Status**: per source (map, targets, pose, laser, camera), seconds since
  the last message, plus the one overall state the page shows as a sentence:
  live, waiting for the map, or robot not connected (all robot sources
  quiet for more than a few seconds).
- **Targets** also carry **seconds since last seen**, for the list's "2 min
  ago".
- **Run**: the run start for the ticker, and
  four series over the run, each thinned to at most ~1 point per 2 s and
  capped in length: battery percent and power (`/telemetry/battery`), speed
  (`/odom` linear speed), and objects found (count of confirmed targets).
  On page load the whole series is sent; after that, new points only.
  - **Run start is a quiet gap** (decided 2026-11-14): the first robot
    message after every robot source has been silent for over ~30 s (or the
    first one ever) starts a new run, clearing the trail and series and
    restarting the ticker.

*Test*: label with no profile falls back to the raw label; lost threshold
at ±1 ms; trail skips sub-threshold moves and drops the oldest past the
cap; a changed `map → odom` shifts every trail point by that transform; a
new page gets the full trail, then only new points; run start empties the
trail; status reports a source never heard from.

## TF01.5 — Local web server

**Status**: done 2026-11-14 — `web_server.py` and `test/test_web_server.py`
run for the first time on the VM (`aiohttp` 3.9.1); **63 tests pass**, `ruff
check` and `ruff format --check` clean on `dome_viz/`, `test/` and
`setup.py`.

- **`web_server.py` needed no changes** — it worked as written.
- **One test did**: it asserted on `caplog.text`, which captures nothing in
  this workspace. ROS's `launch.logging` sets a logger class with
  `propagate = False`, so no record reaches pytest's root handler; the
  `launch_testing` plugins load it before collection. Replaced with a
  `logged_warnings` fixture that attaches a handler straight to the module's
  logger. See `notes.md`, "`caplog` does not work in this workspace".
- `ruff format` also reflowed two lines in `test_floor_plan.py` (first ruff
  run on the package).

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

**Status**: done 2026-11-14 — `bridge_node.py` (269 lines) and
`test/test_bridge_node.py` (11 tests). **74 tests pass**, ruff clean.

- **The camera subscription is reconciled on our own thread.** The server's
  `on_camera_change` runs on the server's thread, and creating or destroying
  a subscription there would race `rclpy`'s executor, so it only records the
  wish under the lock; `reconcile_camera` acts on it from the pose timer
  (10 Hz, so the panel responds within 0.1 s).
- **No rate limiting was added.** `ViewState` already throttles the laser and
  thins the run series, and returns no messages when nothing is new, so the
  `if messages` guard in `feed` is the whole of it.
- **`feed(method, *args)`** holds the lock, appends `now_s` and broadcasts,
  so the six callbacks don't repeat that body.
- **Labels need a path**: parameter `class_profile_path`, defaulting to
  `dome_vision_ros`'s installed `class_profiles.yaml`. **Resolved
  2026-11-15** — and the lookup was broken as well as unconfigured; see
  `chores.md`.
- `package.xml` gained `ament_index_python` (for the installed `static/`) and
  a `geometry_msgs` test dep.
- **Amended 2026-11-15 for I01**: `lookup` now rejects any transform older
  than `TF_STALE_S` (2.0 s). A `tf2` buffer only prunes as new transforms
  arrive, so after a publisher dies its last one was returned for ever — the
  first live run drew a motionless robot and reported it as "live". Two
  regression tests; 76 pass. See `process/05-issues/closed/I01-*`.

**Description**: `bridge_node.py` (ROS adapter):

- `/map` with slam_toolbox's QoS (reliable, transient local), so a page
  opened late still gets the current map.
- `/scan` (sensor-data QoS), for the laser overlay.
- `/telemetry/battery` and `/odom`, for the run graphs.
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

**Status**: done 2026-11-15 — **manual browser test passed**, all eight
steps, against live robot data and `viz01` replay. The user's words: "it all
looks good". Floor plan the right way up and unmirrored, grid and origin,
robot to scale with heading and trail, pan/zoom/Fit/Follow, scale bar, laser
toggle, run ticker, and both themes.

Two follow-ups from the user at the same time: the laser rays were too faint
(chore, done — `globalAlpha` 0.13 → 0.22), and the map should be drawn with
the walls squared up, which became **F02**.

`static/index.html`, `static/app.css`, `static/app.js` (654 lines in all),
ported from the approved mockup. Verified end to end against
`~/.dome/bags/viz01` at 20x: the page and both assets serve with the right
MIME types, and one websocket client received 42 `floor_plan`, 820 `robot`,
162 `trail`, 49 `laser` and 410 `status` messages with no error or warning
from the node. **What is not verified is the rendering itself** — that needs
a browser.

- **No webfont CDN.** The mockup loads Archivo and IBM Plex Mono from Google
  Fonts; the page must work on a LAN with no internet (`notes.md`, "Web
  stack"), so it uses the system stacks those declarations already fell back
  to. The design is otherwise unchanged.
- **The floor grid is flipped on decode.** The `floor_plan` message is in
  `OccupancyGrid` order, row 0 at the lowest y; canvas rows run downwards.
  `decodeFloor` flips once, so every drawing routine can treat field row 0 as
  the top. Checked against a real message: 131x232, base64 decoding to
  exactly 30392 bytes with only the values 0 and 1.
- **The floor raster is the only expensive step**, so it is cached and
  rebuilt only on a new map or a theme change; repaints are coalesced into one
  animation frame. `px` (pixels per cell) is chosen per map so the raster
  never exceeds 2048 on its longer side — at a fixed 8 px/cell a 500x500 room
  would have been a 16 M-pixel stall on the main thread.
- **Included beyond the task's wording**: the coordinate grid, origin marker
  and laser overlay, because `layout.md` puts all three in the Map section and
  neither TF01.7 nor TF01.8 names them; and a waiting-for-the-map state,
  since without it the page is a blank void before the first `/map`.
- **A plain-text connection state** sits where TF01.8's designed status line,
  details panel and offline banner will go. It was needed to test this task at
  all. TF01.8 replaces it.
- **TF01.8's panels belong in their own file**, not appended to `app.js`
  (already 483 lines); it is the map view and should stay that.

**Description**: `index.html` + `app.css` + `app.js`: draw the floor plan
on a canvas in a clean palette (walls dark, free light, unknown as page
background), the robot as an icon with heading, and the trail as a soft
line. Pan with drag, zoom with wheel or pinch, a "follow robot" toggle, and
a scale bar in metres. Redraw only what changed.

*Test*: manual, in a browser against bag replay; record the steps and
result in `current.md`. A JS test toolchain isn't worth adding for this.

## TF01.8 — Page: objects, camera, status

**Status**: **done 2026-11-16.** The sidebar was checked against a live
`viz01` replay on 2026-11-15 and approved ("it looks good").

**The objects half was checked on 2026-11-16**, by the user, against `viz01`
replayed with `dome_semantic` running live on the VM (sim time, fresh
`map_name`). Pins and chips, selection and deselection, lost-object fading,
chip collisions and the list grouping all passed.

**Seen during that run, and left as is (user, 2026-11-16)**: targets that
`dome_semantic` confirms and later withdraws vanish from the page, because
the viewer mirrors each published array. See F01's Decisions.

`static/panels.js` (416 lines) plus the sidebar in `index.html` and its
styles. It owns the object markers, the objects list and detail block, the
camera panel, the status line with its per-source details and the offline
banner, and the four "this run" graphs.

- **The run graphs landed here.** Neither TF01.7 nor TF01.8 named them, but
  `layout.md` has them under "This run" and TF01.1 added them to the approved
  mockup, so they would otherwise have fallen through the gap.
- **`view_state.py` gained one field**: a target entry now carries its raw
  `label`, because the page picks each object's icon and colour from the class
  and the message only had the display name. TF01.1 anticipated exactly this
  ("adjust TF01.4's messages if the layout needs fields they don't carry").
- **A documented seam, not a module system**: `app.js` keeps the map canvas,
  the view transform, the websocket and the controls, and exposes
  `window.domeViz`; `panels.js` owns the DOM. Classic scripts rather than ES
  modules, because module loading is the one thing that cannot be checked
  without a browser.
- **The panels re-render per message type**, not on every message: a 10 Hz
  pose push used to rebuild the status line and redraw four graphs.
- **Verified end to end against `viz01`**: all four assets serve, and one
  websocket client saw 25 `floor_plan`, 881 `targets`, 12 `run`, 881 `status`
  and — after sending `{"type": "camera", "is_on": true}` — **2373 JPEG
  frames**, which proves the camera round-trip and TF01.6's subscription
  lifecycle. Series keys are exactly `battery_pct`, `power_w`, `speed_mps`,
  `objects`.
- **What is unverified is the rendering**, as with TF01.7.

**Description**: Draw each target as a badge with its icon, display name and
ID, readable at any zoom; lost targets faded, not hidden. A camera
picture-in-picture panel, off by default, whose toggle sends camera on/off.
A status line that says plainly when a source has gone quiet ("No map yet",
"Robot not connected").

*Test*: manual, as TF01.7.

## TF01.9 — Launch and make target

**Status**: done 2026-11-15 — `launch/view.launch.py`, `make view` and
`make replay`, with 7 tests in `test/test_launch.py`.

Verified by launching it: `bl dome_viz view.launch.py --port 8094 --host
127.0.0.1` reached the node, the page served 200, and it logged both URLs —
`dome_viz: open http://localhost:8094/` and
`dome_viz: open http://192.168.4.83:8094/`.

- **It uses `better_launch`, not ROS 2 launch** (user's correction; the first
  version used `LaunchDescription` and `DeclareLaunchArgument`). Every DOME
  package launches with `bl`, and this one now matches. See `notes.md`,
  "Launchfiles use `better_launch`".
- **Arguments are the decorated function's typed parameters**, so they arrive
  as real values and all the substitution handling disappeared.
- **`page_urls` moved into the package** (`dome_viz/page_urls.py`): a
  `better_launch` launchfile runs its function at import time, so nothing in
  one can be unit tested. The launchfile is now thin, and `test_launch.py`
  checks the arguments and the `bl.node` call by parsing the file with `ast`.
- **The LAN address comes from the kernel's own routing**, by asking a
  connected UDP socket for its local address. No packet is sent, so it works
  on a LAN with no internet.
- `package.xml` gained a `better_launch` exec dep.

**Description**: `launch/view.launch.py` starts the bridge (args:
`use_sim_time`, `host`, `port`) and prints the page URLs: `localhost` and
the VM's network address. A `make view` target in the
Makefile runs it.

*Test*: a launch-function test with a fake launcher checks the args reach
the node.

## TF01.10 — A replay bag with the map and camera

**Status**: done 2026-11-15 — `~/.dome/bags/viz01` (recorded 2026-11-13) is
the bag, and it is on the VM.

`ros2 bag info` confirms both topics: **`/map` (45) and
`/oak/image_annotated_compressed` (4388)**, over 446 s. The record and replay
commands are in `notes.md`, "Recording and replaying a bag for the viewer",
together with the two traps found while using it — `--clock` and
`use_sim_time` must go together, and two overlapping replays send `/clock`
backwards (issue I02).

It carries no `/semantic/targets` (the semantic node started late) and no
`/telemetry/battery` (disabled on the robot), so the objects list and two of
the four graphs stay empty under this bag. Running `dome_semantic` against
the replay regenerates the targets, which is how
`test/fixtures/viz01replay.json` was made.

**Description**: On the robot, record a short drive with `/map` and
`/oak/image_annotated_compressed` added to the usual topics
(`dome_semantic`'s `notes.md`, "Bag replay of a drive"). Copy it to the
viewer VM. Write the record and replay commands in `notes.md`.

*Test*: manual; needs the robot. `ros2 bag info` shows both topics.

## TF01.11 — Test suite

**Status**: done 2026-11-15 — **85 tests pass**, `ruff check` and
`ruff format --check` clean on `dome_viz/`, `test/`, `launch/` and
`setup.py`.

The end-to-end test is `test/test_end_to_end.py`: `BridgeNode` with its
**real** `WebServer` on a free port, fed a fake `/map`, a `SemanticTarget`
and injected TF, with the assertions made by a real websocket client that
knows only the wire format. It sees the floor plan, a target labelled "soda
can · CN3" from its class profile, and the robot pose composed through
`map -> odom -> base_footprint`. A second case opens a late page and checks
the snapshot matches, which exercises the lock around `on_connect` on the
server's thread.

Per-task tests: TF01.2 `test_imports`, TF01.3 `test_floor_plan` and
`test_wall_fit`, TF01.4 `test_view_state` and `test_run_history`, TF01.5
`test_web_server`, TF01.6 `test_bridge_node` (including I01's two
regressions), TF01.9 `test_launch`.

**TF01.7 and TF01.8 have no automated tests by decision** — their test is
manual in a browser, and a JS toolchain is not worth adding for this. The
browser-side verification that did prove possible is in the task notes above:
every asset serves, and a websocket client sees every message type including
2373 camera frames.

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

## TF01.13 — Lighter fitted walls

**Status**: done 2026-11-16, user approved the second pass ("it looks good now").

**Done before TF01.12**, so the demo shows the finished page; the numbers
follow the order the steps were added, not the order they run.

**Description**: The user found the fitted walls too heavy. `drawWalls`
stroked them at `max(2.5 px, 7 cm)` in near-black ink; halve that to
`max(1.5 px, 3.5 cm)`, then adjust by eye.

**Colour too** (user: "wall color should not be black"): `--wall` goes from
near-black `#28303b` to slate `#5b7088` in light mode, and from `#d9dfe6` to
`#9fb1c4` in dark. The robot's outline used `--wall` as its ink; it now uses
`--fg`, nearly the same colour, so it is unchanged.

**Second pass** (user: still too thick and too dark, and a slightly different
shade): `max(1 px, 2 cm)`; light steel blue `#7f97b2` in light mode, `#7d93ab`
in dark. The Key's wall swatch thinned to match.

*Test*: manual, as TF01.7 — a visual judgement.

## TF01.14 — Show the wall cells as well (experiment)

**Status**: done 2026-11-16, kept by the user.

**Description**: The user wants to see every occupied map cell, not only the
clutter the wall fitter left over. `FloorPlan` gains `wall_cells_xy_m`, the
cells under the fitted lines; the `floor_plan` message carries them as
`wall_cells`; the page draws them as grey squares, like clutter, under the
wall lines.

**Kept** (user, 2026-11-16).

*Test*: `test_wall_cells_and_clutter_cover_every_occupied_cell`; the look is
manual.

## TF01.15 — A key to the map's symbols

**Status**: done 2026-11-16, user approved ("looks good").

**Description**: The user asked for a legend. A "Key" panel at the bottom of
the sidebar, a `<details>` element closed by default, so it needs no
JavaScript. Each entry is a small inline SVG drawn with the map's own colour
tokens, so it follows the theme and any later colour change. Object entries
reuse the real `.marker` pin and chip classes. Entries: robot, trail, fitted
wall, occupied cells, laser, object, object not seen recently, origin and
axes, explored and unexplored floor.

*Test*: manual — each entry checked against the map, in both themes.

