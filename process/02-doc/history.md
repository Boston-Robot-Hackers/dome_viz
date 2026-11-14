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
- **Replay bags copied to the VM's `~/.dome/bags/`** (`viz01` 172 MB with
  `/map` and the camera, `f36run6` 30 MB). Transfers first failed with
  `Received message too long`: the Pi's `~/.bashrc` printed on
  non-interactive sessions, which breaks `rsync`, `scp` and `sftp` alike.
  The `~/rosutils/*.bash` echoes are now guarded with `case $- in *i*)`.
