# Current status

## Open

- **F01, live map view, in progress.** Feature in
  `process/03-features/notdone/`, task file TF01 in `process/04-tasks/notdone/`.
  **TF01.0–TF01.6 done**, and **TF01.7's map renders correctly from live
  robot data** (see `history.md`). **Next: finish TF01.7's checklist, then
  TF01.8**, the whole sidebar — objects list, camera panel, status line and
  the four run graphs. **The graphs do not exist yet**; that is TF01.8, not a
  fault.

- **Open issue I01** (`process/05-issues/open/`): a dead robot still reports
  "live" at a frozen pose. Found on the first live run. Wants a decision, not
  a quick patch — read it before touching `push_pose` or the status logic.

### TF01.7 manual test — part done

**Confirmed in a browser against the live robot on 2026-11-14: the map
renders correctly** — right way up, not mirrored, robot inside the mapped
area. That was the one thing no probe could check, and it means the
`OccupancyGrid` row flip in `decodeFloor` is correct.

**Still unchecked — steps 2 to 8 below.** Nobody has exercised pan, zoom,
Fit map, Follow robot, the scale bar, the Laser toggle or the two themes.
Work through them and record the result here.

Remember: **after any edit under `static/`, `colcon build` and then hard-
reload** (`notes.md`). Two rounds were lost to that and to the `[hidden]`
CSS bug, both now fixed.

Run it, in two terminals:

```
ros2 run dome_viz bridge_node --ros-args -p use_sim_time:=true
ros2 bag play ~/.dome/bags/viz01 --clock
```

Then open `http://localhost:8080/` and check, recording the result here:

1. ~~**The floor plan appears** the right way up and not mirrored.~~
   **Confirmed 2026-11-14 against the live robot.**
2. **The grid and origin**: faint lines, stronger x and y axes, a dot
   labelled `0, 0`, x to the right and y up.
3. **The robot** draws to scale with a heading chevron, and the trail
   follows it as a soft line.
4. **Pan** by dragging, **zoom** on the wheel and with + / −, **Fit map**
   frames the whole map, **Follow robot** keeps it centred and switches off
   as soon as you drag.
5. **The scale bar** changes its labelled length as you zoom.
6. **Laser** toggles the scan overlay.
7. **The run ticker** counts up; the state reads "Live".
8. **Dark and light** both look right (change the OS theme while it runs —
   the floor raster rebuilds on the theme change).

**There is no `launch/` file yet** (that is TF01.9), hence running the node
by hand. **The whole sidebar is missing — camera, the four run graphs and
the objects list are all TF01.8**, so expect only the top bar and the map.

### Running against the live robot

Same thing without `use_sim_time`, which must be off or the node's clock
freezes with no `/clock` publisher:

```
ros2 run dome_viz bridge_node
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
  entirely, so `take_scan`'s lookup failed every time. Same root cause as
  **I01**; it is not a `/scan` QoS problem (the publisher is RELIABLE, and a
  BEST_EFFORT subscriber is compatible with that).

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
- **Literate docs** in `process/01-literate/` cover every Python module,
  through TF01.6. **The page has none**: `.claude/literate.md`'s prompt is
  written for Python ("convert the following Python program"), and the page is
  still half-built. Worth one for `app.js` once TF01.8 lands — decide then
  whether the prompt covers JS.
