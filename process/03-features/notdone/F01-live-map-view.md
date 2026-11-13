# F01 — Live map view on the laptop

**Priority**: High

**Done:** no

**Tasks File Created:** no

**Tests Written:** no

**Test Passing:** no

**Description**: A friendly, good-looking view of the robot's map as it is
built, running entirely on a laptop connected to the robot. It shows the floor
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
  serving happens on the laptop**; the Pi only publishes topics it already
  publishes.

## Architecture

- **A new laptop-side package** (working name `dome_viz`). Nothing in it
  runs on the Pi, and no robot package depends on it.
- **A bridge node on the laptop** subscribes over ROS 2 (the same Wi-Fi DDS
  link RViz already uses) and pushes a simplified state to the browser over a
  local websocket.
- **A web page served on localhost**, opened in the laptop's browser. Its
  HTML, CSS and JS live in their own files, not in Python.
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

- **Laptop-side only.** No web server, bridge or extra node on the Pi.
- **Camera costs Pi load, so it's off by default.** The bridge subscribes to
  the camera topic only while the camera panel is open. `dome_vision` only
  publishes the image when someone is subscribed, so a closed panel costs the
  Pi nothing.
- **Read-only.** The page never publishes anything to the robot.

## Out of scope

- Driving or commanding the robot from the page (teleop, goals, `/intent`).
- Editing the map, naming rooms, moving or deleting targets.
- Opening saved `~/.dome/semantic_maps/*.json` files without ROS running.
- Phones and tablets, or viewing from a second machine on the network.
- Fixing `/targets/markers` in RViz (a `dome_semantic` chore).

## Open questions for the task file

- **Web stack**: plain JS with an HTML canvas, versus a small library for
  pan and zoom. Pick the smallest that looks good.
- **How to clean up the grid**: threshold plus a light morphological
  smoothing, versus drawing wall contours. Try both on `f36run6`.
- **Update rates**: how often to push robot pose and map updates so the page
  feels live without flooding the browser.

## How to Demo

**Setup**: on the laptop, a bag recorded with `/map` and
`/oak/image_annotated_compressed` added to the usual topics, played with
`ros2 bag play <bag> --clock`. The bridge runs with `use_sim_time:=true`, and
the page is open in a browser. **Existing bags such as `f36run6` lack `/map`
and the image**, so either record a new one, or run `slam_toolbox` on the
laptop against the bag's `/scan` to rebuild the map.

**Steps**:
1. Open the page before starting the bag: it says it is waiting for data.
2. Start the bag and watch the floor plan grow as the robot drives.
3. Watch the soda can appear as "soda can · CN1", fade while out of view, and
   come back.
4. Open the camera panel, then close it.
5. Repeat live against the robot, with `top` running on the Pi.

**Expected output**: a clean floor plan with the robot, its trail and the
labelled objects, updating live. With the camera panel closed, the Pi's CPU
is the same as with no laptop viewer connected.

## Process Gate

After creating this feature file and the corresponding task file, **stop and
present the plan to the user**. Do not write any code or content until the
user gives explicit approval to proceed.
