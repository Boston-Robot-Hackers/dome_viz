#!/usr/bin/env python3
# test_imports — every dome_viz module imports cleanly
# Author: Pito Salas and Claude Code
# Version: 1
# Created: 2026-11-14
# Updated: 2026-11-14
# Open Source Under MIT license

import importlib
import pkgutil

import pytest

import dome_viz

MODULE_NAMES = [
    f"dome_viz.{module.name}" for module in pkgutil.iter_modules(dome_viz.__path__)
]


def test_package_has_modules():
    assert MODULE_NAMES


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_imports(module_name):
    importlib.import_module(module_name)
