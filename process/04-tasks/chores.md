# Chores

Running log of simple fixes and refactors (no spec or behavior change). `- [ ] <what and why>` → `- [x]` when applied.
- [x] floor_plan: lock the room's direction only once there is enough wall (200 cells or 3 m fitted); it locked on the first 6-cell map, so an early short wall tilted every wall for the run. Regression test `test_tiny_early_map_does_not_lock_direction`.
- [ ] static/app.js is 538 lines and panels.js 416, both over the style guide's ~300-line smell. app.js is the one to split: the floor raster and the draw* routines are a coherent half that could become map_draw.js. Not urgent, and not worth doing while F02 is about to change the view transform.
- [x] app.js: laser rays were too faint to read at `globalAlpha` 0.13; raised to 0.22 (user's call, 2026-11-15). Hit dots left at 0.6.
- [x] CLAUDE.md: the documented `rosdep install --from-paths src/dome_viz -y` cannot work — `package.xml` depends on `dome_semantic_msgs`, `dome_telemetry_msgs` and `dome_semantic`, which are workspace source packages, so rosdep tries to resolve them as apt keys and fails. Corrected to name all four paths with `--ignore-src`.
