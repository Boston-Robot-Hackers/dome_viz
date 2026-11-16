# History

## 2026-11-13

- **Bootstrapped** from the j3 kit (`~/j3`). Public GitHub repo
  `Boston-Robot-Hackers/dome_viz` created.
- **F01, live map view, approved.** Task file TF01 (TF01.0–TF01.12).
- **TF01.0 done**: aiohttp + plain canvas (`notes.md`, "Web stack").
- **TF01.1 done**: layout agreed (`process/02-doc/layout.md`), mockup in
  `mockup/`, published at https://claude.ai/artifact/H16mhXiNCF5SCbWkBYuQQH,
  then extended with a run ticker and four graphs.
- **Replay bag `viz01` recorded** on the robot: 446 s, with `/map` and
  `/oak/image_annotated_compressed`.

## 2026-11-14

- **TF01.2 done**: `ament_python` package skeleton; builds, import test
  passes. `ruff.toml` ignores `ERA001` (it reads the stamped header lines as
  code).
- **TF01.3 done**: `floor_plan.py` and `wall_fit.py` (thresholds, specks,
  holes, straight wall segments, steady walls between map updates).
  `package.xml` gained `python3-numpy` and `python3-yaml`.
- **TF01.3 bug fix** (`chores.md`): the room's direction now locks only once
  there is enough wall (200 cells or 3 m fitted). It used to lock on the
  first 6-cell map, tilting every wall for the run.
- **TF01.4 done**: `view_state.py` and `run_history.py`. **Run start is a
  quiet gap**: all robot sources silent over 30 s, then a message.
- **Development moved to the viewer VM**: the Pi lacks `aiohttp` and `ruff`.
  Test data copied into `test/fixtures/` (the `f36run6` map; semantic maps
  `f36run6`, `viz01`, `viz01replay`).
- **The VM is set up and verified**: ROS kilted, Python 3.12, `aiohttp`
  3.9.1, `ruff` 0.16.1, `pydantic` 2.13.4; `dome_semantic_msgs`,
  `dome_telemetry_msgs` and `dome_semantic` all present in `~/ros2_ws/src`;
  `core.hooksPath` set to `.githooks`.
- **`CLAUDE.md`'s `rosdep` command was wrong** and could never have worked:
  three `package.xml` deps are workspace source packages, so all four paths
  and `--ignore-src` are needed (`chores.md`).
- **TF01.5 done**: `web_server.py` ran for the first time and needed no
  changes. One test did — `caplog` captures nothing in this workspace
  because ROS's `launch.logging` sets `propagate = False` on every logger
  (`notes.md`). First `ruff` run on the package: clean, two lines reflowed.
- **TF01.6 done**: `bridge_node.py` and 11 tests, passing first run. The
  camera subscription is reconciled on the executor's thread from the pose
  timer, because `on_camera_change` arrives on the web server's thread.
  `package.xml` gained `ament_index_python` and a `geometry_msgs` test dep.
- **TF01.7's page written**: `static/index.html`, `app.css`, `app.js`. The
  map renders correctly from live data — **confirmed in a browser** (the
  `OccupancyGrid` row flip is right). Two bugs found and fixed while testing:
  `element.hidden` could not hide the "waiting for the map" overlay, because
  an author `display: grid` beats the UA stylesheet's `[hidden]` rule on
  origin precedence; and the page's assets must be `colcon build`-ed to reach
  the browser (`notes.md`, "Editing `static/` needs a `colcon build`").
- **First live run against the robot**, rather than a bag. The map, pose and
  run ticker all worked. It exposed **I01**: a dead robot still reports
  "live" at a frozen pose, because `Time()` TF lookups keep succeeding from a
  stale buffer and the pose timer then refreshes its own liveness.
- **Replay bags copied to the VM's `~/.dome/bags/`** (see below)

## 2026-11-15

- **I01 fixed and closed**: `bridge_node.lookup` rejects any transform older
  than `TF_STALE_S` (2 s), because a `tf2` buffer only prunes as new
  transforms arrive, so a dead publisher's last one was returned for ever.
  `ViewState` needed no change — with no pose message, every source falls
  quiet and `QUIET_S` reaches `not_connected` unaided. Verified against a
  publisher that genuinely dies: robot undrawn after 2 s, `not_connected`
  after 7 s.
- **TF01.7 done**: the page's manual browser test passed on all eight steps,
  against live robot data and `viz01`. Laser rays darkened at the user's
  request (a chore).
- **TF01.8 done as far as `viz01` can show it**: `static/panels.js` — object
  markers, objects list and detail, camera panel, status line with
  per-source details, offline banner, and the four run graphs. The user
  approved the page. **The objects half is unverified**, because `viz01`
  carries no `/semantic/targets`. `view_state` gained one field, the raw
  `label`, which the page needs for each object's icon and colour.
  **The camera round-trip is proven**: 2373 JPEG frames after a toggle.
- **TF01.9 done**: `launch/view.launch.py`, `make view`, `make replay`.
  **Rewritten to use `better_launch`** after the user pointed out that every
  DOME package launches with `bl` — which also removed all the substitution
  handling, and moved `page_urls` into the package because a `better_launch`
  launchfile runs at import time and so cannot be unit tested.
- **TF01.10 done**: `viz01` confirmed to carry `/map` and the camera; record
  and replay commands written into `notes.md`.
- **TF01.11 done**: 87 tests, `ruff` clean, including an end-to-end test that
  drives the real bridge and real web server and asserts over a websocket.
- **I02 filed** (open): a backwards `/clock` makes source ages negative, and
  a wrong clock now hides the robot entirely — the second half being a
  consequence of I01's fix that fails silently.
- **F02 filed** (not approved): square up the map so the walls run
  horizontal and vertical. The angle already exists in
  `FloorPlanner.angle_rad`. The user chose to have the grid rotate with the
  map; `layout.md` amended. (`viz01` 172 MB with
  `/map` and the camera, `f36run6` 30 MB). Transfers first failed with
  `Received message too long`: the Pi's `~/.bashrc` printed on
  non-interactive sessions, which breaks `rsync`, `scp` and `sftp` alike.
  The `~/rosutils/*.bash` echoes are now guarded with `case $- in *i*)`.

## 2026-11-16

- **TF01.8 done.** The objects half checked by the user against `viz01`
  replayed with `dome_semantic` live on the VM: pins and chips, selection,
  lost-object fading, chip collisions and list grouping all pass. Recipe in
  `current.md`, "Replaying with objects and a floor plan".
- **Decided: the objects list mirrors `dome_semantic`'s confirmed map**
  (F01, Decisions). Targets it withdraws vanish from the page.
- **Two page bugs fixed** (`chores.md`), both found by the literate docs:
  dragging the map no longer deselects (checked in the browser), and "last
  heard" reports the newest source age (check deferred to TF01.12, since a
  replay never leaves "live").
- **I02 gained a third face**: a stopped `/clock` at the end of a replay pins
  the state at live.
- **`/start` slimmed** to read only `current.md`, synced from `~/j3`;
  `CLAUDE.md` gained the template's "Hazards before any edit" section.
- **Laser no longer lags** (`chores.md`): ~96 % of scans were dropped
  because each was looked up before TF reached its stamp. The newest scan
  now waits and is retried on the pose timer. Measured with a probe on
  `viz01` (24 of 647 resolved before); user confirmed the rays keep up.
- **F01 page tweaks, all approved**: walls thinner and light steel blue
  (TF01.13), every occupied cell drawn as a grey square (TF01.14), a Key
  panel in the sidebar (TF01.15). The object class colours, defined in the
  mockup but never in `app.css`, now are.
- **F02 approved and built**: the view squares the room up, with a Square up
  toggle. Every replay check passed but one, deferred to the live session.
- **`make view` / `make replay`** now say which clock each uses and refuse
  the mix-ups that silently drew no robot (twice today).
