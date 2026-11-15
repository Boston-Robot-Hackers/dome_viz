# I01 A dead robot still reports "live", at a frozen pose

**Closed 2026-11-15.** Fixed by rejecting stale transforms in
`bridge_node.lookup`; see "Resolution" at the end.

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

## Resolution (2026-11-15)

**Chosen fix: reject stale transforms in `bridge_node.lookup`.** It treats
the root cause — a dead publisher's last transform is bad data — and the
status then corrects itself with no change to `ViewState`: no pose message
means `heard("pose")` is never called, every source goes quiet, and
`QUIET_S` does its job.

```python
age_s = self.now_s() - stamp_s(transform.header.stamp)
if age_s > TF_STALE_S:
    return None
```

`TF_STALE_S = 2.0`, chosen against the robot's actual configuration:
`dome_nav/config/mapper_params_online_async.yaml:49` sets slam_toolbox's
`transform_publish_period` to 0.05 s, so the threshold is 40x the publish
period and cannot reject a live transform.

**Rejected alternatives**: stopping the pose timer from counting as a heard
source would have fixed the lying status but left the bridge emitting a
fresh-looking pose from stale transforms; doing both would have added a guard
with no remaining reachable failure, against the style guide.

### Verified end to end

A real `tf2` listener with a publisher that genuinely dies, not a synthetic
buffer. Publisher ran 20 Hz for 6 s, then stopped:

| time | state | pose age | robot messages |
| --- | --- | --- | --- |
| 1-7 s | `waiting_for_map` | 0.0 | 16 -> 76, flowing |
| 8 s | `waiting_for_map` | 1.0 | 76, stopped |
| 12 s | `waiting_for_map` | 5.0 | 76 |
| 13 s | `not_connected` | 6.0 | 76 |

The robot stops being drawn **`TF_STALE_S` after the publisher dies**, and the
page says `not_connected` **`TF_STALE_S` + `QUIET_S` after**. Before the fix,
robot messages climbed for ever with the pose age pinned at 0.0.

### Regression tests

`test_bridge_node.py`, two of them: `test_a_stale_transform_is_treated_as_absent`
(a transform stamped `TF_STALE_S + 3` ago produces no pose push) and
`test_a_stale_pose_leaves_the_state_disconnected` (the state reaches
`not_connected`). The existing pose tests had to move from
`set_transform_static` to dynamic `set_transform` with real stamps, since
`lookup` now judges a transform by its stamp and a static one carries none —
which also makes those tests match production more closely.

### Not fixed, and deliberately

**Under `use_sim_time` with a stopped bag, nothing can go stale**, because
`/clock` stops and the node's clock freezes with it. A paused replay showing
its last state is right, so this needs no guard.

**The laser overlay failing live was the same root cause** and needs no
separate fix: `map` was absent from TF entirely, so `take_scan`'s lookup
failed. It was never a `/scan` QoS problem.
