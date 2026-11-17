# Current status

## Open

### Pick up here (2026-11-16, evening)

- **TF01.16 built and committed**: the robot, trail, laser and object
  markers show from the first odometry, before any map. **Its by-eye check
  is still to run**: a replay that starts before SLAM (task file lists what
  to confirm).
- **Decided**: a finished replay freezes at its last moment; objects stay
  "in view" (`notes.md`).
- **Next after that: the live session** (TF01.12), which needs you and the
  robot.

### Next

- **F01**: then only TF01.12 left, the live demo plus Pi CPU measurements.
- **F02**: closes after its one deferred check, at the live session.
- **TF01.16**: run its by-eye check, then it is done.
- **Warn once when transforms are rejected as stale** (I02's first fix,
  `chores.md`): the wrong clock hid the robot three times today.

### Open issues

- **I02**: a backwards or stopped `/clock` misreports source ages, and a
  wrong clock hides the robot silently. Read it before touching `lookup` or
  the status logic.

### Check on the next live run

- **Last heard**: stop the robot's stack and confirm the status line counts
  up from then, not from the camera's older age (`chores.md`).
- **Selecting an off-screen object** pans it gently into view with Square up
  on (TF02.2).
- **Battery** comes as `/battery`; the bridge reads `/telemetry/battery`,
  which is temporarily off. See which one returns before changing anything.
- **Laser overlay missing live**: SLAM published `/map` but no `map -> odom`
  transform. If it is still missing, file it against `dome_nav`.

### For other repos (no issues filed yet)

- `dome_nav`: slam_manager never saves the map at run end; a manual
  `/slam_toolbox/save_map` failed ("Failed to spin map subscription").
- `dome_semantic`: confirmed 10 false cups on `viz01`, one the can; confirms
  and later withdraws targets early in a run.
- OAK-D crashed on shutdown during the `viz01` drive.
- Pi: `~/.bashrc` exports `ROBOFLOW_API_KEY` in plaintext; move it to an
  untracked sourced file.

### Chores

- Split `static/app.js` (580 lines); F02 has landed, so it is no
  longer blocked (`chores.md`).
