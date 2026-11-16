# Current status

## Open

- **F01, live map view, in progress.** Feature in
  `process/03-features/notdone/`, task file TF01 in `process/04-tasks/notdone/`.
  **TF01.0–TF01.11 are done**, TF01.8 as far as `viz01` can show it. **Next:
  check the objects half of TF01.8** against targets (see below), then
  **TF01.12**, the demo, which needs the robot and you.

- **93 tests pass**, `ruff` clean on `dome_viz/`, `test/`, `launch/` and
  `setup.py`. `make view` and `make replay` work, both through `bl`
  (`notes.md`, "Launchfiles use `better_launch`").

- **Open issues**: **I02** (`process/05-issues/open/`) — a backwards `/clock`
  makes source ages negative, and a wrong clock now hides the robot
  completely and silently. Read it before touching `lookup` or the status
  logic. **F02 + TF02** are filed and *not approved*: squaring up the map, with
  the grid-rotates-with-the-map decision already made.

### TF01.8 — the objects half is still unchecked

The sidebar was checked against a live `viz01` replay and approved: camera
panel, the four graphs, the status line and the responsive collapse all look
right.

**But the objects list was necessarily empty**, because `viz01` has no
`/semantic/targets`. So these are still unverified, and they are half the
point of the feature:

- A pin plus a chip with the class icon and short ID, readable at any zoom.
- Clicking a chip or a list row selects it, shows the detail block, and pans
  **only** if the object was off-screen — never zooming. A second click
  deselects; clicking empty map deselects.
- Lost objects faded with a dashed outline, **never hidden**.
- Where chips would collide, only the pin shows.
- The list groups "In view now" above "Seen earlier".

Two ways to get targets on screen:

```
make replay BAG=~/.dome/bags/f36run6      # 630 targets, but no /map
```

or run `dome_semantic` against the `viz01` replay, which regenerates targets
from its `/oak/detections_3d` — that is how `test/fixtures/viz01replay.json`
was made, and it is the only way to see objects **and** a floor plan at once.

### The map checklist, to re-run after changes

TF01.7's eight steps all passed on 2026-11-15 (`history.md`). Keep them as the
procedure to re-run after TF01.8's objects work and after F02, since both
change what is drawn.

```
bl dome_viz view.launch.py --sim_time True
ros2 bag play ~/.dome/bags/viz01 --clock
```

1. The floor plan the right way up and not mirrored, robot inside it.
2. Grid and origin: stronger x and y axes, a dot labelled `0, 0`.
3. The robot to scale with a heading chevron; the trail fainter at its old end.
4. Pan by dragging; wheel zoom toward the pointer; Fit map; Follow robot,
   which must switch off the moment you drag.
5. The scale bar's width and label changing together.
6. Laser toggling the scan overlay.
7. The run ticker counting up, state reading "Live".
8. Dark and light, changed while it runs — watch for the floor raster keeping
   the old theme's colour.

### Running against the live robot

Same thing without `use_sim_time`, which must be off or the node's clock
freezes with no `/clock` publisher:

```
bl dome_viz view.launch.py
```

**The robot's own stack has to be up first.** With nothing running on the Pi
the VM sees only `/parameter_events` and `/rosout`, and the page correctly
sits on "Waiting for the map". From `dome2/launch/robot.launch.py`'s header:

```
bl dome2 robot.launch.py                            # drivers, control, vision
bl dome_nav robot_map.launch.py --map_name <name>   # Mode A: mapping, gives /map
```

Verified 2026-11-14: discovery needs no setup — both machines have
`ROS_DOMAIN_ID` unset and `ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`, and the
robot answers in ~7 ms.

Two things seen live, neither a `dome_viz` fault:

- **Battery is published as `/battery`, not `/telemetry/battery`.** The
  bridge subscribes to the latter, which is the one that is temporarily
  disabled, so the battery graphs stay empty. Check which topic it comes back
  on before changing anything.
- **The laser overlay never appeared**, because `map` was missing from TF
  entirely, so `take_scan`'s lookup failed every time — SLAM was publishing
  the `/map` grid but not the `map -> odom` transform. Not a `/scan` QoS
  problem (the publisher is RELIABLE, and a BEST_EFFORT subscriber is
  compatible with that). **Worth re-checking on the next live run**: if
  `map -> odom` is still missing while `/map` publishes, that is a robot-side
  SLAM problem to file against `dome_nav`, not against `dome_viz`.

**Target labels work as of 2026-11-15**, and the "which profile path"
decision turned out to be the wrong question: the lookup itself was broken.
`class_profile_path` now defaults to `dome_vision_ros`'s installed
`class_profiles.yaml` — the robot's own vision config, so the viewer cannot
drift from the labels on the camera image — and the bridge joins the
published detector label (`can`) to the profile keyed by `canonical_class`
(`soda can`) through `detector_labels`. Proven against `f36run6`:
`soda can · CN1`, `coffee cup · CP23`. See `chores.md`.

If `dome_vision_ros` is ever absent, the warning says so and targets fall
back to their raw labels, which is `name_and_id`'s designed behaviour.

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
- **Literate docs** cover every module: `01`-`06` for Python, **`07-app`
  and `08-panels` for the page** (added 2026-11-15, after the prompt and
  `process.md` were widened to JavaScript, here and in `~/j3`), plus
  appendices `X01` and `X02`. Their closing observations list two likely
  page bugs worth a chore each: panning probably deselects the selected
  object (`07`, obs. 3), and "last heard" reports the *oldest* source age
  instead of the newest (`08`, obs. 1).
