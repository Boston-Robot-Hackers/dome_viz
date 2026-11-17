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

## Launchfiles use `better_launch`

**Decided 2026-11-15 (user's correction).** Every DOME package launches
through **`better_launch`**, not ROS 2's own launch system — `bl dome_viz
view.launch.py`, matching `bl dome2 robot.launch.py` and the rest. The first
version of `view.launch.py` used `LaunchDescription` and
`DeclareLaunchArgument`; it was rewritten.

**`better_launch` is never to be modified** (user, 2026-11-15). It is a
third-party package in `~/ros2_ws/src`; read it to learn its API, and work
around its behaviour in our own code. Everything about a launch problem gets
fixed in `dome_viz`.

**Do not name a launch argument `use_sim_time`.** It collides with
`better_launch`'s own `--use-sim-time` switch: the declared argument is then
silently never populated, the node runs on wall time, every TF lookup is
stale, and the robot and laser vanish with nothing in the log. **Their own
`--use-sim-time` switch does not help either**: tried on 2026-11-15, the
node's command line carried no `use_sim_time` at all. So the launchfile
declares its own argument, **`sim_time`**, and passes it through `params` as
`use_sim_time`; on the command line that is **`--sim_time True`**.
`test_launch.py` guards both the name and the wiring.

**How to apply**: a launchfile is a `@launch_this`-decorated function whose
typed parameters *are* the launch arguments, with a numpydoc docstring whose
`Parameters` section becomes their help text. Arguments arrive as real
values, so no substitutions:

```python
@launch_this
def view(sim_time: bool = False, host: str = "0.0.0.0", port: int = 8080):
    bl = BetterLaunch()
    bl.node("dome_viz", "bridge_node", "dome_viz_bridge",
            params={"host": host, "port": port, "use_sim_time": sim_time})
```

On the command line the arguments are `--port 8094`, not `port:=8094`.

**A launchfile cannot be imported, so it cannot be unit tested.**
`@launch_this` runs the decorated function at *decoration* time, so importing
`view.launch.py` starts the node. Keep anything worth testing in the package
— `dome_viz/page_urls.py` exists for exactly that — and let the launchfile
stay thin. `test_launch.py` checks the arguments by parsing the file with
`ast`.

## Recording and replaying a bag for the viewer

**TF01.10, 2026-11-15.** `~/.dome/bags/viz01` is the bag the viewer is
developed against. Verified with `ros2 bag info`: 171 MiB, 446 s, with
**`/map` (45) and `/oak/image_annotated_compressed` (4388)** — the two topics
the older F36 bags lack.

**To record another**, on the robot, with its stack already running:

```
ros2 bag record -o ~/bags/<name> \
  /map /tf /tf_static /odom /scan \
  /semantic/targets /oak/detections_3d /oak/image_annotated_compressed \
  /telemetry/battery
```

`/map` is latched (transient local), so it arrives at the start and then only
on each SLAM update — `map_update_interval` is 10 s on this robot, hence only
45 messages in a 7-minute run. Include `/telemetry/battery` once the robot
publishes it again; `viz01` has no battery data because the topic was
disabled when it was recorded.

**To replay it** into the viewer, from the VM:

```
bl dome_viz view.launch.py --sim_time True
ros2 bag play ~/.dome/bags/viz01 --clock
```

Or `make replay BAG=~/.dome/bags/viz01`.

**`--clock` and `use_sim_time:=true` go together.** Without `--clock` nothing
publishes `/clock`, so a node on sim time has a frozen clock; without
`use_sim_time` the node is on wall time while the transforms carry the bag's
stamps, every transform looks days old, and `bridge_node` rejects them all as
stale and draws no robot (see issue I02).

**A finished replay freezes at its last moment, by decision** (2026-11-16).
When the bag ends `/clock` stops, so nothing ages: objects stay "in view",
the run ticker stops. Not a bug; do not add a wall-time fallback.

**Never replay two bags at once**, and restart the viewer between replays:
`/clock` then jumps backwards, which makes source ages negative (I02).

## Bags for replay need `/map` and the image

The `dome_semantic` F36 bags (e.g. `~/.dome/bags/f36run6`) record `/tf`,
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

## Editing `static/` needs a `colcon build`

**Found 2026-11-14 (TF01.7).** The bridge serves the page from the
*installed* `share/dome_viz/static/`, not from `src/`. **Every edit under
`static/` needs `colcon build --packages-select dome_viz`** before it reaches
the browser, and then a hard reload (`Ctrl+Shift+R`) because the browser
caches the CSS and JS.

**`--symlink-install` does not help.** The symlink chain it builds
(`install` → `build` → `src`) is correct, but the page then serves nothing:
`aiohttp`'s `add_static` takes `follow_symlinks=False` by default and refuses
symlinked files. Loosening that for a convenience is not worth it.

**Python changes also need the viewer restarted** (found 2026-11-16, F02).
A running bridge keeps the code it started with, while the page is re-read
on every reload. A new page against an old bridge can break outright: the
page read `angle_rad`, the old bridge never sent it, every screen position
became `NaN`, and the walls vanished. So after a rebuild that touched
`dome_viz/*.py`, `make stop` and relaunch before judging the page.

**How to apply**: after changing the page, rebuild, then hard-reload. If a
change seems to have no effect, `curl` the asset and grep for it before
suspecting the code:
`curl -s http://127.0.0.1:8080/static/app.js | grep <something new>`.

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

## Replaying with objects and a floor plan

**Used for TF01.8's objects check, 2026-11-16.** Three terminals on
the VM, robot stack off. `dome_semantic`'s launchfile has no sim-time
argument, so the node runs through `ros2 run`. Use a fresh `map_name` each
time, or `~/.dome/semantic_maps/<name>.json` is restored at startup.

```
bl dome_viz view.launch.py --sim_time True
ros2 run dome_semantic semantic_map_node --ros-args -r __node:=semantic_map \
  -p use_sim_time:=true -p map_name:=<fresh_name> \
  -p class_profile_path:=$(ros2 pkg prefix dome_semantic)/share/dome_semantic/config/class_profiles.yaml \
  --params-file $(ros2 pkg prefix dome_semantic)/share/dome_semantic/config/semantic_map.yaml
ros2 bag play ~/.dome/bags/viz01 --clock
```

**Targets flicker early in the run**: `dome_semantic` confirms some, then
withdraws them, and the page mirrors that by design (F01, Decisions).

## The map checklist, to re-run after changes

TF01.7's eight steps all passed on 2026-11-15 (`history.md`). Re-run them after
anything that changes what is drawn, such as F02.

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

## Running against the live robot

Launch without `--sim_time`, which must be off here, or the node's clock
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

## Target labels come from the robot's vision config

**Fixed 2026-11-15** (`chores.md`). `class_profile_path` defaults to
`dome_vision_ros`'s installed `class_profiles.yaml`, so the viewer cannot
drift from the labels on the camera image. The bridge joins the published
detector label (`can`) to the profile keyed by `canonical_class` (`soda can`)
through `detector_labels`. Proven against `f36run6`: `soda can · CN1`,
`coffee cup · CP23`.

If `dome_vision_ros` is ever absent, the warning says so and targets fall
back to their raw labels, which is `name_and_id`'s designed behaviour.

## Working on the VM

This clone is `~/ros2_ws/src/dome_viz` on host `vm`; ROS **kilted**, Python
3.12, pytest 7.4.4, `ruff` 0.16.1. No `node`, so JavaScript cannot be
syntax-checked here.

- Do **not** source `/opt/ros/<distro>/setup.bash` by hand in a tool call —
  the shell already has ROS from the user's profile. Only
  `source install/setup.bash` is needed before pytest.
- `caplog` captures nothing here; see "`caplog` does not work in this
  workspace".

## The replay bags

**They live in `~/.dome/bags/`**, not `~/bags/`. Over GitHub's 100 MB limit,
so never `git add` them.

| topic | `viz01` (171 MiB, 446 s) | `f36run6` (29 MiB, 387 s) |
| --- | --- | --- |
| `/map` | 45 | — |
| `/oak/image_annotated_compressed` | 4388 | — |
| `/oak/detections_3d` | 4388 | 3865 |
| `/semantic/targets` | — | 630 |
| `/odom` | 10460 | 11542 |
| `/scan` | 3966 | 3826 |
| `/tf` / `/tf_static` | 24305 / 2 | 25564 / 1 |

**Neither bag has `/telemetry/battery`, and that is expected**: the topic is
temporarily disabled on the robot and will return (user, 2026-11-14). The
battery and power graphs therefore stay empty under these bags. **Don't treat
that as a bug or add code for it**: `ViewState` already tolerates a source
that never publishes, which gets no key in `heard_s` at all.

**`viz01` has no `/semantic/targets`**; running `dome_semantic` against it
regenerates them (see "Replaying with objects and a floor plan"). One such
run is saved as `test/fixtures/viz01replay.json`.
