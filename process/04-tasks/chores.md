# Chores

Running log of simple fixes and refactors (no spec or behavior change). `- [ ] <what and why>` → `- [x]` when applied.
- [x] floor_plan: lock the room's direction only once there is enough wall (200 cells or 3 m fitted); it locked on the first 6-cell map, so an early short wall tilted every wall for the run. Regression test `test_tiny_early_map_does_not_lock_direction`.
