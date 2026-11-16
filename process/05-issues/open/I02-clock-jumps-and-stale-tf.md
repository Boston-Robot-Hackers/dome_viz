# I02 A backwards or stopped clock misreports ages, and a wrong clock hides the robot

## Symptom

Three faces of one cause — the node's clock and the transform stamps
disagreeing.

**1. Negative source ages.** Seen 2026-11-15 while replaying `viz01`:

```
status: live  ages: {map: 7.5, pose: -377.6, laser: 11.5, odom: 0.3, ...}
```

`pose` is 377 s in the *future*. The page would print "-377.6 s", and
`ViewState.status_message`'s `is_connected` test (`age <= QUIET_S`) counts a
negative age as connected, so the state is pinned at live.

**2. `TF_OLD_DATA` floods, and no robot at all.** With a bag playing and a TF
listener on wall time:

```
[WARN] TF_OLD_DATA ignoring data from the past for frame odom
       at time 1794620131.391642 according to authority default_authority
```

The warning's own stamp is wall clock (`1794769047`, today); the data is
stamped when the bag was recorded (`1794620131`). Every transform looks about
two days old, so **`bridge_node.lookup`'s `TF_STALE_S` check rejects all of
them** and the robot is never drawn.

**3. A stopped clock pins the state at live.** Seen 2026-11-16 at the end
of a `viz01` replay: the bag finished, and the page kept saying "Live" while
the run ticker stopped. With `/clock` silent, a sim-time node's `now` stops at
the bag's last stamp, so every source age freezes below `QUIET_S` and nothing
ever goes stale. **Replay only**: on the robot the bridge is on wall time,
which keeps running.

It also means the not-connected status line, including "last heard", cannot
be reached on a replay at all — so that line can only be checked live.

## Cause

`ViewState` ages are `now_s - heard_s`, both read from the node clock. Under
`use_sim_time` that clock is the bag's, and it is **not monotonic across
runs**: restarting a replay, or running two overlapping ones, sends it
backwards. Anything heard before the jump then sits in the future.

The second face is the mirror image: forget `-p use_sim_time:=true` and the
node is on wall time while the transforms carry bag stamps, so every
transform is stale by the age of the recording.

**Face 2 is a behaviour change from I01's fix** (2026-11-15). Before the
staleness check, a wall-clock node replaying a bag drew the robot from
stamp-ignoring `Time()` lookups. It now draws nothing. The new behaviour is
more honest — those transforms really are not current — but it fails
*silently*, because `lookup` logs the rejection at debug level.

## Tests already done

- **Not reproducible in a clean single replay**: one bridge, one bag, 126
  status messages, no negative age on any source. The negative age came from
  my own overlapping replays.
- Confirmed the clean case is well behaved, so this is about clock
  discontinuities, not ordinary running.

## Latest theory / candidate fixes

Three separable pieces; none is urgent, and the first is the one with teeth.

- **Make the stale rejection visible.** Warn once (not per lookup, which is
  10 Hz) when transforms are being rejected as stale, naming the age — it
  turns a silent blank map into "your clock is wrong". Cheap, and it catches
  the commonest mistake of all, a forgotten `use_sim_time`.
- **Treat a backwards clock as a new run.** `ViewState.heard` already starts
  a fresh run after a forward gap of `RUN_GAP_S`; a *backwards* jump is just
  as much a new run, and handling it there would clear the trail and series
  and drop the stale `heard_s` values in one move. This is the tidiest fix
  and needs a decision about where it belongs. **This was foreseen**:
  `process/01-literate/04-view_state.md`'s closing observations already note
  that "bag replay restarted with no pause won't trigger a new run, because
  simulated time jumps backwards rather than forwards", and that treating a
  backwards jump as a gap "would be one more comparison".
- **Clamp ages at zero** in `status_message`. Smallest, but it only hides the
  symptom, so it should not be done alone.

**Gets a regression test** when fixed: a `ViewState` fed a message, then
`tick`ed with a `now_s` *earlier* than the one it was fed, must not report a
negative age or claim to be connected on the strength of one.

## Not a bug

The `TF_OLD_DATA` warnings themselves come from `tf2`, not from `dome_viz`,
and are correct: it is refusing to overwrite newer data with older. They are
a symptom to read, not something to silence.
