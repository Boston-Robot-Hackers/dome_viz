---
version: "1.0"
generated: "2026-11-15"
---

# Appendix: the launchfile, and why it is nearly empty

Two small files start the viewer: `launch/view.launch.py` and
`dome_viz/page_urls.py`. The split between them is the only interesting thing
about either, and it is forced by how `better_launch` works.

## A launchfile is a function

Every DOME package launches through **`better_launch`** rather than ROS 2's own
launch system, so `view.launch.py` is a decorated function whose *typed
parameters are the launch arguments*:

```python
@launch_this
def view(use_sim_time: bool = False, host: str = "0.0.0.0", port: int = 8080):
    bl = BetterLaunch()
    bl.node("dome_viz", "bridge_node", "dome_viz_bridge",
            params={"host": host, "port": port}, use_sim_time=use_sim_time)
```

Compare this with the ROS 2 equivalent it replaced: a `LaunchDescription`
holding a list of `DeclareLaunchArgument` objects, a `Node` whose parameters
are `LaunchConfiguration` substitutions, and a `LogInfo` whose message had to
be assembled from alternating strings and substitutions because the port was
not a number until launch time. **Here `port` is simply an `int`**, so the
URLs are an f-string.

The docstring is not decoration either: `better_launch` parses its
`Parameters` section into the help text for `bl dome_viz view.launch.py -h`.

## The catch: it runs at import

`@launch_this` does not register the function for later. It calls
`_exec_launch_func` **at decoration time**, which means *importing* the module
launches the node. That single fact shapes everything else:

- **Nothing in a launchfile can be unit tested**, because a test that imports
  it starts a bridge and never returns.
- So anything worth testing has to live outside it. That is why
  `page_urls.py` exists as a module in the package rather than as two
  functions in the launchfile — it is the part with actual behaviour, and it
  is covered by real tests.
- What remains in the launchfile is checked by *reading* it. `test_launch.py`
  parses the file with `ast` and asserts on the decorated function's
  arguments and defaults, and on the `bl.node` call. That catches the realistic
  failure — an argument renamed, removed, or silently re-defaulted — without
  ever executing the module.

## Finding the machine's own address

The viewer runs on the VM, but the page is usually opened on the Mac as well,
so the launcher prints both URLs. Getting the LAN address without a
dependency is a nice small trick:

```python
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
    probe.connect(OFF_SUBNET)
    return probe.getsockname()[0]
```

`connect` on a **UDP** socket sends nothing. It only asks the kernel to pick a
route, and picking a route assigns the local address the kernel *would* use to
reach that destination — which is exactly the interface address other machines
on the LAN can reach. So this works on an isolated network with no internet,
which matters: the whole page is built to work on a LAN with no route out.

Parsing `ip addr` would have needed a guess about which interface is the real
one; `hostname -I` returns several on a machine with Docker, as this VM has.
Asking the routing table dodges both problems.

The `OSError` branch returns `None` rather than inventing an address, and
`page_urls` then prints only the localhost URL. A machine with no route out is
a real case — it is what you get on a laptop with the wifi off.

## Observations

- **`OFF_SUBNET` is a public DNS address** (`8.8.8.8`) used purely as a
  routing hint. Nothing is sent to it, but it reads like an internet
  dependency at a glance, and a reader has to be told it is not. A documented
  constant is the cheapest mitigation; a reserved address such as
  `192.0.2.1` would read better but relies on a default route existing.
- **The `ast` tests are a workaround, not a win.** They cannot check that the
  node actually receives the parameters, only that the source says so. The
  end-to-end check is that `bl dome_viz view.launch.py --port N` really
  serves on N, which was done by hand.
- **`make replay` backgrounds the launcher and kills it with `kill %1`**,
  which is fine interactively and poor in a script. If it ever needs to be
  reliable, the two processes want a proper supervisor.
