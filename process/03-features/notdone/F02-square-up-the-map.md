# F02 — Square up the map

**Priority**: Medium

**Approved:** 2026-11-16, by the user.

**Done:** no

**Tasks File Created:** yes

**Tests Written:** yes

**Test Passing:** yes

**Description**: Draw the map rotated so the room's **main wall direction
runs horizontally and vertically** on screen, instead of at whatever angle the
robot happened to start its run at.

SLAM's `map` frame is oriented by wherever the robot was switched on, so a
rectangular room usually arrives tilted by some arbitrary few degrees. Walls
that are square in the world come out visibly skewed, which reads as sloppy
and makes the picture harder to interpret at a glance.

The floor-plan pipeline **already computes this angle** and already holds it
steady: `FloorPlanner.angle_rad` is the room's main direction, re-estimated
only until there is enough wall and then locked for the rest of the run
(`floor_plan.py`, TF01.3). This feature carries that number through to the
page and rotates the view by it. **No new estimation, no new maths.**

## Why

Straight walls read as straight. It is the single biggest remaining
difference between the view and a floor plan a person would draw, and it
costs almost nothing because the angle is already known and already stable.

## Scope

- The rotation applies to **everything drawn in map metres**: floor raster,
  walls, clutter, trail, robot, laser, and later TF01.8's object markers.
- **The angle is the robot's, not the user's.** No manual rotate control; it
  comes from the map and changes only when the planner's own direction
  changes (which it stops doing once locked).
- **A toggle** so the view can be put back to true `map` orientation, since
  that is what RViz shows and is sometimes what you want when comparing.

## Not in scope

- Letting the user pick an arbitrary rotation.
- Re-orienting the saved map itself, or anything on the robot. This is a
  display choice in the viewer only; `map` frame coordinates are untouched
  and every number the page reports stays in the `map` frame.

## Open question for the task plan

**What happens to the coordinate grid and the `0, 0` marker.**
`process/02-doc/layout.md` currently specifies a grid "in the `map` frame"
with "x pointing right and y pointing up", which a rotated view contradicts.
Either the grid rotates with the map (axes no longer screen-aligned) or it
stays screen-aligned (and no longer means `map` x and y). **`layout.md` must
be updated either way** — this feature changes an agreed layout decision.

## How to Demo

**Setup**: the bridge running against `~/.dome/bags/viz01` with
`use_sim_time`, the page open.

**Steps**:
1. Open the page and look at the walls of the mapped room.
2. Toggle the squaring control off and on.

**Expected output**: with it on, the room's long walls run left-right and
up-down on screen; with it off, the map returns to the tilt it has today.
Nothing else about the picture changes, and the robot still sits in the right
place relative to the walls in both.

## Process Gate

After creating this feature file and the corresponding task file, **stop and
present the plan to the user**. Do not write any code or content until the
user gives explicit approval to proceed.
