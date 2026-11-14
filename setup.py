#!/usr/bin/env python3
# setup — ament_python packaging for dome_viz
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license
"""Installs the dome_viz package, its page (`static/`) and launch files."""

from glob import glob

from setuptools import find_packages, setup

package_name = "dome_viz"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/static", glob("static/*")),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="pitosalas",
    maintainer_email="pitosalas@gmail.com",
    description="Friendly, read-only web view of the DOME robot's map.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "bridge_node = dome_viz.bridge_node:main",
        ],
    },
)
