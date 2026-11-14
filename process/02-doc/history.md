# History

## 2026-11-13

- **Bootstrapped** from the j3 kit (`~/j3`). Public GitHub repo
  `Boston-Robot-Hackers/dome_viz` created.
- **F01, live map view, approved.** Task file TF01 (TF01.0–TF01.12).
- **TF01.0 done**: aiohttp + plain canvas (`notes.md`, "Web stack").
- **TF01.1 done**: layout agreed (`process/02-doc/layout.md`), mockup in
  `mockup/`, published at https://claude.ai/artifact/H16mhXiNCF5SCbWkBYuQQH,
  then extended with a run ticker and four graphs.
- **Replay bag `viz01` recorded** on the robot: 446 s, with `/map` and
  `/oak/image_annotated_compressed`.

## 2026-11-14

- **TF01.2 done**: `ament_python` package skeleton; builds, import test
  passes. `ruff.toml` ignores `ERA001` (it reads the stamped header lines as
  code).
- **TF01.3 done**: `floor_plan.py` and `wall_fit.py` (thresholds, specks,
  holes, straight wall segments, steady walls between map updates).
  `package.xml` gained `python3-numpy` and `python3-yaml`.
- **TF01.3 bug fix** (`chores.md`): the room's direction now locks only once
  there is enough wall (200 cells or 3 m fitted). It used to lock on the
  first 6-cell map, tilting every wall for the run.
- **TF01.4 done**: `view_state.py` and `run_history.py`. **Run start is a
  quiet gap**: all robot sources silent over 30 s, then a message.
- **Development moved to the viewer VM**: the Pi lacks `aiohttp` and `ruff`.
  Test data copied into `test/fixtures/` (the `f36run6` map; semantic maps
  `f36run6`, `viz01`, `viz01replay`).
