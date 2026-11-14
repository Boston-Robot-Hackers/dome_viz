---
version: "1.0"
generated: "2026-11-14"
---

# bridge_node: the only place ROS and the page meet

Every other module in `dome_viz` is deliberately ignorant. `floor_plan` and `wall_fit` know about numpy grids; `view_state` and `run_history` know about dictionaries that happen to serialise as JSON; `web_server` knows about sockets. **None of them import `rclpy`.** `bridge_node` is where that ignorance is paid for: it is the single adapter that turns the robot's topics into `ViewState` calls, and `ViewState`'s messages into websocket traffic.

This is the *ports and adapters* shape, and the payoff is visible in the test suite: 63 of the project's 74 tests need no ROS graph at all.

## The shape of the thing

```mermaid
flowchart TB
    subgraph rclpy executor thread
        T1[/map, /scan, /semantic/targets/]
        T2[/telemetry/battery, /odom/]
        TF[TF buffer]
        P[push_pose @ 10 Hz]
        K[push_tick @ 1 Hz]
    end
    subgraph shared
        V[ViewState]
    end
    subgraph web server thread
        C[on_connect]
        M[on_camera_change]
    end
    T1 --> F[feed]
    T2 --> F
    P --> F
    K --> F
    TF --> P
    F -- under self.lock --> V
    C -- under self.lock --> V
    V --> B[broadcast to pages]
    M -. records a wish .-> P
```

Two threads reach `ViewState`, and that is the central fact the module is built around.

## One lock, one funnel

`ViewState` is explicitly not thread-safe — its docstring says the bridge holds a lock. The temptation is to sprinkle `with self.lock:` through six callbacks. Instead there is one funnel:

```python
def feed(self, method, *view_args) -> None:
    """One `ViewState` call under the lock, and its messages to the pages."""
    with self.lock:
        messages = method(*view_args, self.now_s())
    if messages:
        self.server.broadcast(messages)
```

Three things are worth noticing:

- **The lock is held for the `ViewState` call only**, not the broadcast. `broadcast` just serialises and hands off via `call_soon_threadsafe`, so holding the lock across it would serialise the two threads for no reason.
- **`now_s()` is read inside the lock**, so the timestamps a `ViewState` sees are ordered the same way its calls are.
- **`method` is a bound method of `view`**, passed in rather than named by string. Each callback reads as `self.feed(self.view.on_map, occupancy_of(grid))` — the ROS-to-plain-data conversion sits in the call, and the locking discipline sits in one place.

The `if messages` guard does double duty as the module's rate limiting. `ViewState` already throttles the laser to ~5 Hz and thins graph series to a point every two seconds; when it has nothing new it returns an empty list, and nothing crosses to the browser. **No throttling code was added here**, because there was nothing left to throttle.

## Time, so replay works

```python
def now_s(self) -> float:
    """Node time, so `use_sim_time` carries through to bag replay."""
    return self.get_clock().now().nanoseconds * 1e-9
```

Reading the *node's* clock rather than `time.time()` is what makes `ros2 bag play --clock` work: with `use_sim_time` set, "now" is the bag's time. `ViewState`'s run ticker, lost-target timeouts and quiet-gap run detection are all expressed in these seconds, so they all follow replay for free.

## Pose is a TF question, not a topic

There is no pose topic. The robot's position is a TF lookup on a timer, and it takes **two** of them:

```python
robot_in_odom = self.lookup(ODOM_FRAME, ROBOT_FRAME, latest)
map_from_odom = self.lookup(MAP_FRAME, ODOM_FRAME, latest)
if robot_in_odom is None or map_from_odom is None:
    return
```

Why not simply ask for `map → base_footprint`, which is one call and gives the answer directly? Because `ViewState` keeps the **trail in the `odom` frame** and re-projects it through the current `map → odom` on every send. When slam_toolbox closes a loop, `map → odom` jumps, and the whole trail moves with the map instead of being left cutting through walls. The bridge must therefore hand over the two transforms separately — the decomposition is load-bearing, not incidental.

A failed lookup returns `None` and the push is skipped:

```python
except TransformException as error:
    self.get_logger().debug(f"no transform {parent} -> {child}: {error}")
    return None
```

This is the one place where "return `None` on a problem" is the right answer rather than a style violation: TF not yet having a transform is a **normal startup and replay condition**, not an error, and the alternative — inventing a pose — would draw the robot somewhere it has never been.

The laser follows the same pattern but asks at the scan's *own* stamp, `Time.from_msg(scan.header.stamp)`, so rays are placed where the lidar was when it swept, not where the robot is now.

## The camera, and a thread you must not touch

The project's governing constraint is that the viewer must cost the Pi nothing when nobody is looking (`notes.md`, "Keep the Pi's load unchanged"). `dome_vision` only encodes images when something subscribes, so the bridge subscribes **only while a page has the panel open**.

The obvious implementation is to create and destroy the subscription inside `on_camera_change`. That callback, however, arrives on the *web server's* thread, and `rclpy`'s node is not safe to mutate from under its spinning executor. So the callback refuses to do the work:

```python
def on_camera_change(self, is_wanted: bool) -> None:
    """Also the server's thread: only record the wish, never subscribe."""
    with self.lock:
        self.is_camera_wanted = is_wanted
```

and the pose timer — which already runs on the executor at 10 Hz — reconciles it:

```python
if is_wanted and self.camera_subscription is None:
    self.camera_subscription = self.create_subscription(...)
elif not is_wanted and self.camera_subscription is not None:
    self.destroy_subscription(self.camera_subscription)
    self.camera_subscription = None
```

This is the *deferred reconciliation* pattern: a foreign thread writes desired state, the owning thread converges actual state onto it. The cost is up to 100 ms of latency on a panel toggle, which no user can perceive. The benefit is that no framework object is ever mutated from the wrong thread.

The test encodes exactly this, including the part that would be invisible otherwise:

```python
node.on_camera_change(True)
assert node.camera_subscription is None, "must wait for our own thread"
node.reconcile_camera()
assert node.camera_subscription is not None
```

## Conversions as free functions

The ROS-message-to-plain-data translations are module-level functions, not methods: `occupancy_of`, `targets_of`, `scan_of`, `pose2d_of`, `yaw_of`, `stamp_s`. They need no node, so they take none, and they can be read and reasoned about without the class.

`yaw_of` is the only one with real content — the standard quaternion-to-yaw reduction, which collapses to two terms once you only want rotation about *z*:

```python
along = 2.0 * (quaternion.w * quaternion.z + quaternion.x * quaternion.y)
across = 1.0 - 2.0 * (quaternion.y**2 + quaternion.z**2)
return math.atan2(along, across)
```

Using `atan2` rather than `asin` keeps all four quadrants, so a robot facing backwards reads as ±π rather than wrapping to zero.

## Observations

- **`class_profile_path` defaults to empty**, which makes targets display a raw label and a two-letter prefix (`CA7`) instead of `soda can · CN1`. `dome_semantic` does not install its `class_profiles.yaml`; the only installed copy belongs to `dome_vision_ros`. This wants settling at TF01.9, either as a launch default or a vendored copy.
- **The 10 Hz pose timer does two jobs** — pose pushes and camera reconciliation. It works and it avoids a second timer, but the coupling is incidental; a reader could reasonably expect `reconcile_camera` to live on its own timer.
- **Topic names are constants, not parameters.** Fine for one robot; the moment a second namespace appears they should become declared parameters.
- **A silent source is handled, but by `ViewState`, not here.** `/telemetry/battery` is currently disabled on the robot and simply never arrives. Nothing in the bridge notices or needs to, because `is_connected` is an `any` over source ages and the run-gap check uses the most recent message from *any* source.
