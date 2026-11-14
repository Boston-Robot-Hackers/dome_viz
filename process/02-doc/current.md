# Current status

## Open

- **F01, live map view, in progress.** Feature in
  `process/03-features/notdone/`, task file TF01 in `process/04-tasks/notdone/`.
  TF01.0–TF01.4 done (see `history.md`). **TF01.5, local web server, in
  progress**; see "Finish TF01.5" below. Then TF01.6, the bridge node.

### Development is on the viewer VM (decided 2026-11-14)

**Work on the VM, not the Pi.** The Pi lacks `aiohttp` and `ruff`, so
TF01.5 can't be tested there. The Pi copy (`~/ros2_ws/src/dome_viz` on
`dome-R1`) is pushed and no longer where work happens.

#### 1. Get the work onto the VM

- `git clone` (or `git pull`) `Boston-Robot-Hackers/dome_viz` into the VM's
  `~/ros2_ws/src`. Everything through the 2026-11-14 checkpoint is pushed.
- **Test data in the repo**: `test/fixtures/` holds the `f36run6` floor plan
  (`.pgm` + `.yaml`) and the semantic maps `f36run6.json`, `viz01.json` and
  `viz01replay.json` (from the Pi's `~/.dome/semantic_maps/`).
- **Replay bags are not in the repo** (`viz01_0.mcap` is 180 MB, over
  GitHub's 100 MB limit). **The user copies them to the VM by hand**, from
  the Pi's `~/bags/viz01` (180 MB; `/map` and the camera; for TF01.10 and
  the demo) and `~/bags/f36run6` (31 MB, no `/map`), into the VM's
  `~/bags/`. Never `git add` them.
- Unpushed commits in `dome_vision`, `dome_control` and `dome_semantic` are
  separate; push them if the VM needs them.

#### 2. Set up the VM (once)

- `git config core.hooksPath .githooks` in the clone, so file headers stamp.
- **The workspace needs** `dome_semantic_msgs`, `dome_telemetry_msgs` and
  `dome_semantic` (the tests import `dome_semantic.class_profiles`, which
  needs `pydantic`). Whether the VM already has them is **unverified**; if
  not, clone them into the VM's `~/ros2_ws/src` too.
- From `~/ros2_ws`: `rosdep install --from-paths src/dome_viz -y` (installs
  `python3-aiohttp`), then `colcon build --packages-select dome_viz`.
- Install `ruff`.

#### 3. Check the state

- `source install/setup.bash && python3 -m pytest src/dome_viz/test`. On
  the Pi (no `aiohttp`): 56 passed, and `test_web_server.py` can't be
  collected (run with `--ignore` on it; `test_imports[web_server]` fails).
  On the VM all of it should run.
- **`ruff check` and `ruff format --check` have never been run** on
  `dome_viz/*.py`, `test/*.py`, `setup.py`. Only pyflakes and an 88-column
  check are clean. Fix what ruff finds.

#### 4. Finish TF01.5 (local web server)

- **`dome_viz/web_server.py` and `test/test_web_server.py` are written but
  have never run.** Run the tests first and fix what fails.
- **The server**: `WebServer(ServerConfig(static_dir, host, port),
  on_connect, on_camera_change)`, `start()` / `stop()`,
  `broadcast(messages)`, `send_camera(jpeg)`.
  - Own thread and asyncio loop. `GET /` is `index.html`, `/static/...` the
    rest of `static_dir`, `/ws` the websocket.
  - **One outgoing queue per page**, so a new page's snapshot (from
    `on_connect()`, i.e. `ViewState.snapshot`) always comes before deltas,
    and a slow page doesn't hold up others.
  - The page sends `{"type": "camera", "is_on": bool}`. The server calls
    `on_camera_change(is_wanted)` only when the number of pages with the
    camera on goes from zero to one or back, including when such a page
    closes. JPEGs go as binary frames, only to those pages. Other page
    messages are logged as a warning and ignored.
  - `static_dir` is passed in (the bridge finds the installed `share/`), so
    the module has no ROS imports.
- **The tests** start a real server on a free port on `127.0.0.1`:
  index and static fetch, bound address, port clash raises, two pages get
  the snapshot then a broadcast, camera toggle and frames only to camera
  pages, malformed page message logged.
- **Then**: mark TF01.5 done in the task file. **Next is TF01.6**, the
  bridge node. It must hold a lock around every `ViewState` call, since
  the web server's `on_connect` runs on the server's thread.

### Other open items

- **Replay bag `viz01`** (TF01.10's bag, already recorded): its targets from
  a bag replay are in `test/fixtures/viz01replay.json`. The live semantic
  node started late and missed the can.
- **Found on the `viz01` drive, for other repos (no issues filed yet)**:
  `dome_nav`'s slam_manager never saves the map at the end of a run, and a
  manual `/slam_toolbox/save_map` failed ("Failed to spin map
  subscription"); `dome_semantic` confirmed 10 false cups, one of them the
  can read as a cup; the OAK-D crashed on shutdown.
- **Literate docs** in `process/01-literate/` cover the modules through
  TF01.5; `web_server`'s describes untested code.
