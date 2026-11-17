---
version: "1.1"
generated: "2026-11-15"
---

# Appendix: the package skeleton

These files make `dome_viz` an installable ROS 2 `ament_python` package. There is little logic in them, but a few choices matter.

## `bridge_node.py`'s entry point

The node itself is now the subject of `06-bridge_node.md`; what belongs here is
only its `main`, which is the package's one console script.

```python
try:
    rclpy.spin(node)
except (KeyboardInterrupt, ExternalShutdownException):
    pass  # Ctrl-C or the launcher's SIGTERM: a normal stop
finally:
    node.destroy_node()
    rclpy.try_shutdown()
```

When a launch stops the node, Kilted's rclpy has already shut the context down and `spin()` raises `ExternalShutdownException`. It counts as a normal stop, like Ctrl-C, so no traceback is printed. `try_shutdown` rather than `shutdown` avoids an error in that same case.

## `setup.py`

- **`static/` and `launch/`** are installed into `share/dome_viz/` by glob. The bridge will find the page there with `get_package_share_directory`, and pass that path to the web server.
- **One console script**, `bridge_node`.

## `package.xml`

- **`<depend>`**: `rclpy`, the message packages (`nav_msgs`, `sensor_msgs`, `tf2_ros`, `dome_semantic_msgs`, `dome_telemetry_msgs`).
- **`<exec_depend>`**: `dome_semantic` (class profiles), `python3-aiohttp`, `python3-numpy`.
- **`<test_depend>`**: `python3-pytest`, `python3-yaml` (the test that loads the `.pgm` fixture).

`rosdep install --from-paths src/dome_viz -y` installs the system ones on a new machine.

## `test/test_imports.py`

It lists every module in the package with `pkgutil.iter_modules` and imports each in its own parametrised test. A new module is covered automatically, and a missing dependency shows up as one clearly named failure, as `web_server` does on the Pi today.

## Observations

- **`dome_semantic` is a full runtime dependency** for one small, ROS-free module (`class_profiles`). If `dome_semantic` ever grows heavy imports at package level, moving the profiles into `dome_semantic_msgs` or a shared config package would keep the viewer light.
- The import test and `web_server` tests fail on a machine without `aiohttp`. That is correct (it is a declared dependency), but explains the Pi's one red test.
