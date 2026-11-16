# TF02 Square up the map, for Feature F02

**Date Created:** 2026-11-15

For each task step, add a test when feasible. If not feasible, note why.

**Shape**: the angle already exists in `FloorPlanner.angle_rad`. Carry it
through `FloorPlan` and the `floor_plan` message, then apply it in the page's
view transform — one rotation in `toScreen`/`toWorld`, which every drawing
routine already goes through.

## TF02.0 — Decide what the grid does

**Status**: done 2026-11-15. **The grid rotates with the map** (user's
call).

- Every number on screen stays honest: `0, 0`, the axis arrows and the edge
  labels all keep meaning `map` x and y.
- The cost: grid lines sit a few degrees off the window edges.
- `layout.md`'s Map section is updated.

**Description**: Settle the one open question in F02: with the view rotated,
does the coordinate grid rotate with the map, or stay screen-aligned?

- **Rotate with the map**: the grid keeps meaning `map` x and y, the `0, 0`
  marker and axis arrows stay correct, but the grid lines sit at an angle to
  the screen, which partly defeats the tidiness the feature is for.
- **Stay screen-aligned**: lines stay parallel to the window edges, but they
  no longer correspond to `map` x and y, so the metre labels along the edges
  become misleading and the axis arrows would have to go.

Recommendation to put to the user: **rotate the grid with the map.** It keeps
every number on screen honest, and the walls — which is what the eye actually
reads as "square" — still come out straight. A grid at 3 degrees is barely
noticeable; mislabelled axes are a real error.

Update `process/02-doc/layout.md`'s Map section with the decision, since it
currently specifies x right and y up.

*Test*: none. It's a decision.

## TF02.1 — Carry the angle to the page

**Status**: done 2026-11-16.

### What was done

- **`FloorPlan.angle_rad`** is the planner's angle, 0.0 until it has one.
- **The message sends `view_angle_rad` of it**, wrapped from 0 to pi/2 into
  plus or minus pi/4, so the view always takes the smallest turn: a room at
  80 degrees turns by -10, not 80.
- **Tests**:
  - `test_rotated_room_segments_follow_its_angle` (extended);
  - `test_a_map_with_no_wall_reports_angle_zero`;
  - `test_floor_plan_message_encodes_floor` (extended);
  - `test_view_angle_is_the_smallest_turn`.

**Description**: `FloorPlan` gains an `angle_rad` field, set from
`FloorPlanner.angle_rad`; `floor_plan_message` adds it as `angle_rad` (0.0
when the planner has no direction yet, so the page always has a number).
No change to how it is computed.

*Test*: `test_floor_plan.py` — the fitted plan reports the angle the planner
locked, and a map with too little wall reports 0.0. `test_view_state.py` —
the `floor_plan` message carries it.

## TF02.2 — Rotate the view

**Status**: done 2026-11-16, except one check deferred to the next live
session.

### What was done

- **One rotation, `viewRot()`**, inside `toScreen` and `toWorld`.
- **The raster** is drawn under `ctx.rotate`.
- **`drawGrid`** draws map-x and map-y lines over the four corners' bounds,
  and labels them where they cross the top and left edges.
- **The origin arrows and the robot's heading** add the turn.
- **`fit`** takes its bounds in the turned frame.
- **Pan, wheel zoom and `bringIntoView`** go through `toWorld`, so they stay
  exact.
- **Clutter and wall-cell squares stay screen-aligned.** They are a few
  pixels across, so turning them is not worth the cost.

### What was checked

On a `viz01` replay, by the user, all passing:

- walls run square;
- dragging does not drift;
- wheel zoom stays about the pointer;
- Fit map frames the room in both modes;
- the toggle keeps the robot against the walls;
- the grid labels read right.

**Deferred to the next live session**: selecting an off-screen object pans
it gently into view. It needs targets, which plain `viz01` lacks.

**Description**: In `app.js`, apply the angle in the view transform so every
drawing routine inherits it:

- `toScreen` / `toWorld` rotate by `-angle` / `+angle` about the view centre.
  Both must stay exact inverses, or dragging and wheel-zoom will drift.
- The floor raster is an axis-aligned image in map space, so it needs
  `ctx.rotate` around the right pivot rather than a rotated `drawImage` rect.
- `fit()`'s bounding box must be computed **in rotated space**, or Fit map
  will leave the room off-centre or clipped.
- Pan deltas are in screen pixels and must be un-rotated before being added
  to `state.cx` / `state.cy`.

*Test*: manual, in a browser — a JS test toolchain still isn't worth adding
(same reasoning as TF01.7). Check: walls run square; dragging moves the map
with the pointer and does not drift; wheel zoom still zooms about the
pointer; Fit map frames the room; the robot stays in the same place relative
to the walls as the toggle flips.

## TF02.3 — The toggle

**Status**: done 2026-11-16. The user checked that the button matches the
view and that the choice survives a reload.

### What was done

- **A `Square up` button** after Laser, `aria-pressed`, on by default.
- **The choice is kept in `localStorage`** under `domeViz.isSquared`,
  wrapped in try/catch so the view works without storage.
- **The view turns about its centre**, so toggling leaves the same spot in
  the middle.

**Description**: A **Square up** button in the map controls, beside Laser,
pressed by default. Off returns the view to true `map` orientation. Remember
the choice in `localStorage` so it survives a reload, since it is a per-viewer
preference and not robot state.

*Test*: manual. The button's pressed state matches the view, and the choice
survives a reload.

## TF02.4 — Test suite

**Status**: done 2026-11-16, except the deferred TF02.2 check.

- TF02.1's tests exist and pass (97 in all), and `ruff` is clean.
- The manual results are recorded in TF02.2 and TF02.3.
- **F02 closes after the deferred check.**

**Description**: Make sure TF02.1's tests exist and pass, `ruff` is clean,
and the manual steps from TF02.2 and TF02.3 are recorded in `current.md` with
their result.

*Test*: this step is the tests.
