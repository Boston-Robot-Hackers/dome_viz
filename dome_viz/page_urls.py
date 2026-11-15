#!/usr/bin/env python3
# page_urls — the addresses the viewer's page can be opened at
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-15
# Updated: 2026-11-15
# Open Source Under MIT license
"""Works out the URLs the launch file prints when it starts the viewer.

Its own module rather than part of the launch file because a `better_launch`
launch file runs its function at import time, so nothing in one can be unit
tested.
"""

import socket

OFF_SUBNET = ("8.8.8.8", 1)


def lan_address() -> str | None:
    """This machine's address on the LAN, or None if it has no route out.

    Asks the kernel which local address it would use to reach something off
    the subnet. A connected UDP socket sends no packets, so this needs no
    network and works on a LAN with no internet.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(OFF_SUBNET)
            return probe.getsockname()[0]
    except OSError:
        return None


def page_urls(port: int) -> list:
    """Always localhost, plus the LAN address when the machine has one.

    The viewer runs on the VM but the page is usually opened on the Mac too,
    so both are worth printing.
    """
    urls = [f"http://localhost:{port}/"]
    address = lan_address()
    if address:
        urls.append(f"http://{address}:{port}/")
    return urls
