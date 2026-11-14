# Current status

## Open

- **Bootstrapped 2026-11-13** from the j3 kit (`~/j3`, in sync with GitHub).
  No code yet.
- **F01, live map view: approved 2026-11-13, in progress.** Feature in
  `process/03-features/notdone/`, task file TF01 (TF01.0–TF01.12) in
  `process/04-tasks/notdone/`. **TF01.0 done** (aiohttp + plain canvas,
  `notes.md`). **TF01.1 done**: layout agreed, in `process/02-doc/layout.md`;
  mockup in `mockup/` (published at
  https://claude.ai/artifact/H16mhXiNCF5SCbWkBYuQQH), extended the same
  day with a run ticker and four graphs. **Next: TF01.2, package skeleton.**
- **Open decision before TF01.2**: ruff's `ERA001` flags the header lines
  the pre-commit hook stamps (`# Version:`, `# Created:`, `# Updated:`) as
  commented-out code, on every `.py`. Like `EXE001`, a rule clash: turn it
  off in `ruff.toml`, or not? Ask the user.
- **Not pushed**: `e8837f0`, `a59d2e8` (and earlier unpushed commits in
  `dome_vision`, `dome_control`, `dome_semantic`).
- **Replay bag for TF01.10 recorded**: `~/bags/viz01` on the robot (446 s,
  with `/map` and `/oak/image_annotated_compressed`). Not yet copied to the
  VM. Its targets from a bag replay are in
  `~/.dome/semantic_maps/viz01replay.json` (the live semantic node started
  late and missed the can).
- **Found on the `viz01` drive, for other repos (no issues filed yet)**:
  `dome_nav`'s slam_manager never saves the map at the end of a run, and a
  manual `/slam_toolbox/save_map` failed ("Failed to spin map
  subscription"); `dome_semantic` confirmed 10 false cups, one of them the
  can read as a cup; the OAK-D crashed on shutdown.
- **On GitHub**: public repo `Boston-Robot-Hackers/dome_viz`, created
  2026-11-13.
- **The repo lives in the robot's workspace for now** (`~/ros2_ws/src` on
  `dome-R1`), but it runs on the viewer VM (Ubuntu in VMware on the Mac mini). Clone it
  there to run it.
