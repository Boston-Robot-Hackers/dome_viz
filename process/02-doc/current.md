# Current status

## Open

### Pick up here (2026-11-16)

- **TF01.8 done**: the objects check passed on a `viz01` replay with
  `dome_semantic` live; two page bugs fixed (`chores.md`).
- **Next: TF01.12**, the demo on the live robot, which needs you. At it, run
  the "last heard" chore's manual check, which a replay cannot reach (I02).
- `.claude/` synced from `~/j3` (`process.md`, `style_guide.md`,
  `/checkpoint`, `/start`, the session-start hook); `settings.json` kept.

### Next

- **F01, live map view**: TF01.0–TF01.11 done; TF01.12 left. Feature and
  task file in `notdone/`. 93 tests pass.
- **F02 + TF02, squaring up the map**: filed, *not approved*. Re-run the map
  checklist (`notes.md`) after it.

### Open issues

- **I02**: a backwards or stopped `/clock` misreports source ages, and a
  wrong clock hides the robot silently. Read it before touching `lookup` or
  the status logic.

### Check on the next live run

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

- Split `static/app.js` (542 lines); parked until F02 changes the view
  transform (`chores.md`).
