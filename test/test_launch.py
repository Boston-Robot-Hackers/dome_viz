#!/usr/bin/env python3
# test_launch — the remote launchfile's arguments, and the URLs it prints
# Author: Pito Salas and Claude Code
# Version: 3
# Created: 2026-11-15
# Updated: 2026-11-19
# Open Source Under MIT license
"""Reads the launchfile as source, and tests the URL helper for real.

**The launchfile cannot be imported.** `better_launch`'s `@launch_this` runs
the decorated function at decoration time, so importing `remote.launch.py`
would start the bridge. The launch arguments are therefore checked by parsing
the file with `ast`, which is enough to catch the thing that breaks silently:
an argument renamed, removed, or given a different default.

`page_urls` lives in `dome_viz.page_urls` precisely so it *can* be tested,
and it is, below.
"""

import ast
from pathlib import Path

from dome_viz.page_urls import lan_address, page_urls

LAUNCH_FILE = Path(__file__).resolve().parent.parent / "launch" / "remote.launch.py"


def launch_function() -> ast.FunctionDef:
    """The one function in the launchfile decorated with `launch_this`."""
    tree = ast.parse(LAUNCH_FILE.read_text())
    decorated = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any("launch_this" in ast.dump(item) for item in node.decorator_list)
    ]
    (function,) = decorated
    return function


def arguments() -> dict:
    """The launch arguments and their defaults, as written in the signature."""
    function = launch_function()
    names = [argument.arg for argument in function.args.args]
    defaults = [ast.literal_eval(default) for default in function.args.defaults]
    assert len(names) == len(defaults), "every launch argument needs a default"
    return dict(zip(names, defaults, strict=True))


def node_call() -> ast.Call:
    """The `bl.node(...)` call inside the launch function."""
    calls = [
        node
        for node in ast.walk(launch_function())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "node"
    ]
    (call,) = calls
    return call


def test_declares_sim_time_host_and_port():
    assert set(arguments()) == {"sim_time", "host", "port"}


def test_argument_defaults_serve_the_lan_on_8080():
    assert arguments() == {"sim_time": False, "host": "0.0.0.0", "port": 8080}


def test_it_starts_the_bridge():
    call = node_call()
    package, executable = (ast.literal_eval(arg) for arg in call.args[:2])
    assert (package, executable) == ("dome_viz", "bridge_node")


def test_the_arguments_reach_the_node_as_parameters():
    """The node parameter is `use_sim_time`; the launch argument feeding it is
    `sim_time`, and the two names must stay different."""
    call = node_call()
    keywords = {keyword.arg: keyword.value for keyword in call.keywords}
    params = keywords["params"]
    assert [ast.literal_eval(key) for key in params.keys] == [
        "host",
        "port",
        "use_sim_time",
    ]
    assert [value.id for value in params.values] == ["host", "port", "sim_time"]


def test_no_launch_argument_is_called_use_sim_time():
    """Regression guard. That name collides with `better_launch`'s own
    `--use-sim-time` switch, and the declared argument is then silently never
    populated: the node runs on wall time, every TF lookup is stale, and the
    robot and laser vanish with nothing in the log."""
    assert "use_sim_time" not in arguments()


def test_page_urls_always_offers_localhost():
    urls = page_urls(8080)
    assert urls[0] == "http://localhost:8080/"


def test_page_urls_adds_the_lan_address_when_there_is_one():
    address = lan_address()
    urls = page_urls(9999)
    if address is None:
        assert len(urls) == 1
    else:
        assert urls[1] == f"http://{address}:9999/"


def test_page_urls_uses_the_port_it_is_given():
    assert all(":4242/" in url for url in page_urls(4242))
