"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Generic hypervisor support classes.
"""

from __future__ import annotations

import importlib
import os
import sys

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, "../"))

if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

print_log = getattr(importlib.import_module("constants"), "print_log")

# Import shared run_cmd so this module does not duplicate its definition.
from utils.process import run_cmd  # pylint: disable=wrong-import-position,import-error


class GenericHypervisor:
    """Base hypervisor helper with source management and build helpers."""

    def __init__(self, wrkdir, srcs_path=""):
        """
        Initialize generic hypervisor paths and source metadata.

        Args:
            wrkdir (str): Framework working directory.
            srcs_path (str): Optional path to pre-existing hypervisor sources.
        """
        self.wrkdir = wrkdir
        self.srcs_path = srcs_path
        self.git_repo = ""
        self.git_rev = ""

    def fetch_sources(self, hypervisor_srcs):
        """Fetch or select hypervisor sources in subclasses."""

    def clone_hypervisor(self, git_repo, git_rev, srcs_path): # pylint: disable=no-self-use
        """Clone the hypervisor sources and checkout the requested revision."""
        git_dir = os.path.join(srcs_path, ".git")
        if not os.path.exists(git_dir):
            print_log("INFO", "Fetching hypervisor sources...", tab_level=2)
            run_cmd(["git", "clone", git_repo, srcs_path])
            run_cmd(["git", "checkout", git_rev], cwd=srcs_path)
            return
        print_log("INFO", "Hypervisor sources already present.", tab_level=2)

    def clean(self, directory): # pylint: disable=no-self-use
        """Run the hypervisor clean target in the given directory."""
        run_cmd(["make", "clean"], cwd=directory)


class StandaloneGenericHypervisor:
    """Hypervisor shim for standalone guest binaries."""

    def __init__(self, wrkdir):
        self.srcs_path = wrkdir

    def fetch_sources(self, _hypervisor_srcs):  # pylint: disable=no-self-use
        """No sources to fetch for standalone mode."""

    @staticmethod
    def build(  # pylint: disable=too-many-arguments,unused-argument
        wrkdir_imgs,
        config_repo,
        config_name,
        platform,
        env,
    ):
        """Return the expected standalone output artifact names."""
        bin_name = "guest1.bin"
        elf_name = "guest1.elf"
        out_img = os.path.join(wrkdir_imgs, bin_name)
        return out_img, bin_name, elf_name

    @staticmethod
    def clean(directory):  # pylint: disable=unused-argument
        """Do nothing for standalone artifacts."""


generic_hypervisor = GenericHypervisor  # pylint: disable=invalid-name
standalone = StandaloneGenericHypervisor  # pylint: disable=invalid-name
