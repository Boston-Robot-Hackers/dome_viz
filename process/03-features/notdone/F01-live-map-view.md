# F01 — Live map view

**Priority**: High

**Done:** no

**Tasks File Created:** yes

**Tests Written:** no

**Test Passing:** no

**Description**: A friendly, good-looking view of the robot's map as it is
built, running entirely on a viewer machine connected to the robot (an Ubuntu
VM in VMware on the Mac mini), and opened in any browser on the network. It shows the floor
plan, the objects the robot has found, where the robot is and has been, and
what the camera sees. It is meant to be easy to understand at a glance, for
people who don't know RViz: **cleaned up and less detailed than the raw
topics, not a debugging tool.**

## Why

- **RViz shows everything, raw.** Grid cells, TF frames, 8 cm marker spheres
  that vanish at map zoom. That's right for debugging and wrong for watching
  the robot work or showing it to someone.
- **The Pi has no CPU to spare** (I02 power and load work, TF33.9). A web
  page served from the Pi would add load there. **All the rendering and
  serving happens on the viewer VM**; the Pi only publishes topics it already
  publishes.

## Architecture

- **A new package for the viewer VM** (`dome_viz`), an Ubuntu VM in VMware
  on the Mac mini. Nothing in it runs on the Pi, and no robot package depends
  on it.
- **A bridge node on the VM** subscribes over ROS 2 (Wi-Fi DDS, so the VM
  needs bridged networking) and pushes a simplified state to the browser over
  a websocket.
- **The VM serves the page on the local network.** Open it in the VM's own
  browser or from any browser on the same network (e.g. Safari on the Mac
  mini). Every page shares the one bridge, so more viewers add no load on the
  Pi. Its HTML, CSS and JS live in their own files, not in Python.
- **It only reads topics**, so it works the same against the live robot and
  against `ros2 bag play` of a recorded run (with `use_sim_time`), e.g.
  `~/bags/f36run6`. That also lets it be built and tested without the robot.

## Scope

| Panel | Source | Cleaned-up as |
|---|---|---|
| **Floor plan** | `/map` (`OccupancyGrid`, slam_toolbox) | Walls drawn as clean dark lines or fills, free space light, unknown space as plain background. No grid, no noise specks. Redrawn as SLAM updates it. |
| **Objects** | `/semantic/targets` (`SemanticTargetArray`) | An icon or badge per target with its display name and ID (e.g. "soda can · CN1"). Lost targets shown faded, not hidden. Size readable at any zoom. |
| **Robot** | TF `map → base_footprint` | A robot icon with heading, plus a trail of where it has driven this session. |
| **Camera** | `/oak/image_annotated_compressed` | A picture-in-picture view of the annotated image, which the user can switch off. |

- **Pan and zoom** the map; **follow the robot** as an option.
- **Display names and abbrevs** come from `dome_semantic`'s
  `config/class_profiles.yaml` (`display_name`, `abbrev`), so the view and
  the robot agree on names.
- **Connection status**: the page says plainly when it has no data (robot
  off, Wi-Fi down, no SLAM) instead of showing a stale or empty map silently.

## Decisions

- **Viewer VM only.** No web server, bridge or extra node on the Pi.
- **Served on the local network, no login.** The server listens on all the
  VM's interfaces by default (a `host` parameter can narrow it to
  `127.0.0.1`). It is read-only, but anyone on the network can see the map
  and the camera, so it's for a trusted home or lab network.
- **Camera costs Pi load, so it's off by default.** The bridge subscribes to
  the camera topic only while the camera panel is open. `dome_vision` only
  publishes the image when someone is subscribed, so a closed panel costs the
  Pi nothing.
- **Read-only.** The page never publishes anything to the robot.

## Out of scope

- Driving or commanding the robot from the page (teleop, goals, `/intent`).
- Editing the map, naming rooms, moving or deleting targets.
- Opening saved `~/.dome/semantic_maps/*.json` files without ROS running.
- A layout designed for phones and tablets (desktop browsers only).
- Logins, HTTPS, or viewing from outside the local network.
- Fixing `/targets/markers` in RViz (a `dome_semantic` chore).

## Open questions for the task file

- **Web stack**: plain JS with an HTML canvas, versus a small library for
  pan and zoom. Pick the smallest that looks good.
- **How to clean up the grid**: threshold plus a light morphological
  smoothing, versus drawing wall contours. Try both on `f36run6`.
- **Update rates**: how often to push robot pose and map updates so the page
  feels live without flooding the browser.

## How to Demo

**Setup**: on the viewer VM, a bag recorded with `/map` and
`/oak/image_annotated_compressed` added to the usual topics, played with
`ros2 bag play <bag> --clock`. The bridge runs with `use_sim_time:=true`, and
the page is open in a browser. **Existing bags such as `f36run6` lack `/map`
and the image**, so either record a new one, or run `slam_toolbox` on the
VM against the bag's `/scan` to rebuild the map.

**Steps**:
1. Open the page before starting the bag, in the VM's browser and in a
   browser on the Mac: both say they are waiting for data.
2. Start the bag and watch the floor plan grow as the robot drives.
3. Watch the soda can appear as "soda can · CN1", fade while out of view, and
   come back.
4. Open the camera panel, then close it.
5. Repeat live against the robot, with `top` running on the Pi.

**Expected output**: a clean floor plan with the robot, its trail and the
labelled objects, updating live. With the camera panel closed, the Pi's CPU
is the same as with no viewer connected, however many pages are open.

## Process Gate

After creating this feature file and the corresponding task file, **stop and
present the plan to the user**. Do not write any code or content until the
user gives explicit approval to proceed.
