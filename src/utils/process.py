# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.
"""Utility functions for running subprocesses in the Bao Kao Framework."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys


def run_command(command, cwd=None, env=None):
    """Run a command and raise RuntimeError on failure."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        if details:
            raise RuntimeError(f"Command failed: {' '.join(command)}\n{details}")
        raise RuntimeError(f"Command failed: {' '.join(command)}")
    return result.stdout


run_cmd = run_command


def setup_framework_path():
    """Add the framework root to sys.path and return it."""
    cur = os.path.dirname(os.path.abspath(__file__))
    fw_path = os.path.abspath(os.path.join(cur, "../.."))
    if fw_path not in sys.path:
        sys.path.append(fw_path)
    return fw_path


def get_print_log():
    """Return the print_log function from the constants module."""
    return getattr(importlib.import_module("constants"), "print_log")
