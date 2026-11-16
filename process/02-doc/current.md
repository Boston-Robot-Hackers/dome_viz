# Current status

## Open

### Pick up here (2026-11-16, later)

- **F01 page tweaks done and approved**: lighter steel-blue walls (TF01.13),
  wall cells drawn as grey squares (TF01.14), a Key panel (TF01.15). Chores:
  laser scans no longer dropped, class colours defined, `make view` /
  `make replay` guard against the wrong clock.
- **F02 approved and built**: Square up passed every replay check but one.
- **Next: the live session** (TF01.12), which needs you and the robot.

### Next

- **F01**: only TF01.12 left, the live demo plus Pi CPU measurements.
- **F02**: closes after its one deferred check, at the live session.
- **Warn once when transforms are rejected as stale** (I02's first fix):
  the wrong clock has silently hidden the robot twice today.

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
