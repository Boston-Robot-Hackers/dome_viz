# I01 A dead robot still reports "live", at a frozen pose

## Symptom

**Observed live on 2026-11-14**, with the real robot. The robot's whole stack
had gone away — `ros2 node list` showed only `/dome_viz_bridge` and my own
probe nodes — and yet the bridge kept telling the page:

```
state: "live"
ages_s: {map: 42.7, odom: 38.9, pose: 0.0, laser: None, ...}
robot: 61 messages in 6 s
```

`pose` is **0.0 s old** while every real source is 40 s stale. The page would
draw the robot, at its last position, with a green "Live" status, for as long
as the viewer is left open. It should say "Robot not connected".

## Cause

`bridge_node.push_pose` looks up TF at `Time()`, meaning *latest available*:

```python
latest = Time()
robot_in_odom = self.lookup(ODOM_FRAME, ROBOT_FRAME, latest)
map_from_odom = self.lookup(MAP_FRAME, ODOM_FRAME, latest)
```

A `tf2` buffer only prunes old transforms **as new ones are inserted**. When
the publishers stop, whatever it last held stays there, and a `Time()` lookup
goes on returning it with no staleness limit. So:

1. Both lookups keep succeeding from stale buffer contents.
2. `ViewState.on_pose` is called, which calls `heard("pose")`.
3. `heard` refreshes `pose`'s timestamp to *now*.
4. `status_message`'s `is_connected` is `any(age <= QUIET_S ...)`, and `pose`
   is always 0.0 s, so the state is pinned at `live` forever.

**The pose timer manufactures its own liveness.** Every other source is driven
by an arriving message, so its age means something; `pose` is driven by our own
10 Hz timer and means only "the timer ran".

`odom -> base_footprint` is also static-ish in practice, so even the robot
disappearing entirely does not break the lookup.

## Tests already done

- Confirmed the robot's nodes were gone (`ros2 node list`).
- Confirmed `map -> odom` is genuinely absent now: a **freshly started**
  listener (`tf2_echo map odom`, and a purpose-built probe) reports
  `LookupException: "map" ... does not exist`, because a new listener only
  learns frames from `/tf` messages that arrive after it subscribes. The
  long-running bridge still has the frame cached. That difference is what
  makes the bug invisible from the command line.
- Confirmed the `/scan` path fails for the *same* root cause while `map` is
  missing: `take_scan` returns before `feed`, so `laser` is never even marked
  heard — hence `laser: None` above.

## Latest theory / candidate fixes

Not fixed yet; it is a design choice, so it wants a decision rather than a
quick patch.

- **Require the transform to be recent.** `lookup_transform` returns a stamped
  transform; compare `header.stamp` with the node clock and treat anything
  older than a threshold as absent. Honest, and local to `lookup`.
- **Don't let the pose timer count as a heard source.** Keep drawing the robot
  but stop `on_pose` refreshing `pose`'s age — liveness would then come only
  from genuinely arriving messages (`map`, `odom`, `scan`, `targets`).
- **Both.** The first fixes the frozen pose, the second fixes the lying status.

Whichever is chosen, `view_state.py`'s `QUIET_S` logic itself is sound and
needs no change — it was given a source that lies about its age.

**Gets a regression test** when fixed: feed a pose, advance the clock past
`QUIET_S` with no further messages, and assert the state is `not_connected`.
That is a pure `ViewState` test; the TF-staleness half is hardware-only.
