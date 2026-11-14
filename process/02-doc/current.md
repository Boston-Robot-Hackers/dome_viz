# Current status

## Open

- **F01, live map view, in progress.** Feature in
  `process/03-features/notdone/`, task file TF01 in `process/04-tasks/notdone/`.
  **TF01.0–TF01.6 done** (see `history.md`). **Next is TF01.7**, the page's
  floor plan, robot, pan and zoom — the first browser-side task.

### Next: TF01.7, the page

The server side is complete: **74 tests pass**, `ruff` clean. TF01.7 and
TF01.8 are browser work (`static/index.html`, `app.css`, `app.js`), starting
from the approved mockup in `mockup/` — see `process/02-doc/layout.md`.
Their tests are manual, in a browser against bag replay.

**There is no `launch/` file yet** (that is TF01.9), so start the bridge by
hand:

```
ros2 run dome_viz bridge_node --ros-args -p use_sim_time:=true
ros2 bag play ~/.dome/bags/viz01 --clock
```

**One open decision, due at TF01.9.** `bridge_node`'s `class_profile_path`
parameter defaults to `""`, which makes targets show a raw label and a
two-letter prefix (`CA7`) instead of "soda can · CN1". `dome_semantic` does
not install its `class_profiles.yaml` — the only installed copy belongs to
`dome_vision_ros`. Either point the launch default at that package's share
directory (and add the dependency), or vendor a copy in `dome_viz`.

### Working on the VM

This clone is `~/ros2_ws/src/dome_viz` on host `vm`; ROS **kilted**, Python
3.12, pytest 7.4.4, `ruff` 0.16.1.

- Do **not** source `/opt/ros/<distro>/setup.bash` by hand in a tool call —
  the shell already has ROS from the user's profile. Only
  `source install/setup.bash` is needed before pytest.
- `caplog` captures nothing here; see `notes.md`, "`caplog` does not work in
  this workspace".

### The replay bags

**They live in `~/.dome/bags/`**, not `~/bags/` as earlier notes said. Over
GitHub's 100 MB limit, so never `git add` them.

| topic | `viz01` (171 MiB, 446 s) | `f36run6` (29 MiB, 387 s) |
| --- | --- | --- |
| `/map` | 45 | — |
| `/oak/image_annotated_compressed` | 4388 | — |
| `/oak/detections_3d` | 4388 | 3865 |
| `/semantic/targets` | — | 630 |
| `/odom` | 10460 | 11542 |
| `/scan` | 3966 | 3826 |
| `/tf` / `/tf_static` | 24305 / 2 | 25564 / 1 |

**Neither bag has `/telemetry/battery`, and that is expected** — the topic is
**temporarily disabled on the robot and will return** (user, 2026-11-14).
Nothing to re-record, no issue to file. Two of the four sidebar graphs
(battery percent, power draw) therefore **stay empty under these bags**;
speed and objects-found are unaffected. **Don't treat the empty graphs as a
bug**, and don't add code for the absence: `ViewState` already tolerates a
source that never publishes (checked 2026-11-14 — `is_connected` is an
`any(...)` over source ages at `view_state.py:209`, and `heard()` compares
against `max(heard_s.values())` at `view_state.py:138`, while a source never
heard from gets no key at all).

**`viz01` has no `/semantic/targets`** — it has `/oak/detections_3d`, so
running `dome_semantic` live against the replay regenerates them (that is how
`test/fixtures/viz01replay.json` was made).

### Other open items

- **Replay bag `viz01`** (TF01.10's bag, already recorded): its targets from
  a bag replay are in `test/fixtures/viz01replay.json`. The live semantic
  node started late and missed the can.
- **Found on the `viz01` drive, for other repos (no issues filed yet)**:
  `dome_nav`'s slam_manager never saves the map at the end of a run, and a
  manual `/slam_toolbox/save_map` failed ("Failed to spin map
  subscription"); `dome_semantic` confirmed 10 false cups, one of them the
  can read as a cup; the OAK-D crashed on shutdown.
- **Noticed on the Pi, outside this project**: `~/.bashrc` exports
  `ROBOFLOW_API_KEY` in plaintext. Worth moving to an untracked file that
  `.bashrc` sources, since dotfiles tend to end up in repos.
- **Literate docs** in `process/01-literate/` cover every module through
  TF01.6.
