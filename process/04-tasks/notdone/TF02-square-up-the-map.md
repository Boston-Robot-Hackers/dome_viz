# TF02 Square up the map, for Feature F02

For each task step, add a test when feasible. If not feasible, note why.

**Shape**: the angle already exists in `FloorPlanner.angle_rad`. Carry it
through `FloorPlan` and the `floor_plan` message, then apply it in the page's
view transform — one rotation in `toScreen`/`toWorld`, which every drawing
routine already goes through.

## TF02.0 — Decide what the grid does

**Status**: done 2026-11-15 — **the grid rotates with the map** (user's
call). Every number on screen therefore stays honest: `0, 0`, the axis
arrows and the edge labels all keep meaning `map` x and y, at the cost of
grid lines sitting a few degrees off the window edges. `layout.md`'s Map
section updated.

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

**Status**: not done

**Description**: `FloorPlan` gains an `angle_rad` field, set from
`FloorPlanner.angle_rad`; `floor_plan_message` adds it as `angle_rad` (0.0
when the planner has no direction yet, so the page always has a number).
No change to how it is computed.

*Test*: `test_floor_plan.py` — the fitted plan reports the angle the planner
locked, and a map with too little wall reports 0.0. `test_view_state.py` —
the `floor_plan` message carries it.

## TF02.2 — Rotate the view

**Status**: not done

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

**Status**: not done

**Description**: A **Square up** button in the map controls, beside Laser,
pressed by default. Off returns the view to true `map` orientation. Remember
the choice in `localStorage` so it survives a reload, since it is a per-viewer
preference and not robot state.

*Test*: manual. The button's pressed state matches the view, and the choice
survives a reload.

## TF02.4 — Test suite

**Status**: not done

**Description**: Make sure TF02.1's tests exist and pass, `ruff` is clean,
and the manual steps from TF02.2 and TF02.3 are recorded in `current.md` with
their result.

*Test*: this step is the tests.
