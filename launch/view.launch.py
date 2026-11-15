#!/usr/bin/env python3
# view.launch.py — start the bridge and print the page's URLs
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-15
# Updated: 2026-11-15
# Open Source Under MIT license
"""Starts `bridge_node` and logs the addresses the page can be opened at.

A `better_launch` launchfile, like the rest of the DOME packages: run it with
`bl dome_viz view.launch.py`, or `make view`.

`host` defaults to 0.0.0.0 so the page is reachable from the Mac as well as
from the VM's own browser.
"""

from better_launch import BetterLaunch, launch_this

from dome_viz.page_urls import page_urls


@launch_this
def view(use_sim_time: bool = False, host: str = "0.0.0.0", port: int = 8080):
    """Serve the live map view.

    Parameters
    ----------
    use_sim_time : bool, optional
        Follow /clock, for bag replay. Must be true whenever a bag is played
        with --clock, and false otherwise.
    host : str, optional
        Address to serve on; 0.0.0.0 is every interface.
    port : int, optional
        Port to serve the page on.
    """
    bl = BetterLaunch()
    bl.node(
        "dome_viz",
        "bridge_node",
        "dome_viz_bridge",
        params={"host": host, "port": port},
        use_sim_time=use_sim_time,
    )
    for url in page_urls(port):
        bl.logger.info(f"dome_viz: open {url}")
