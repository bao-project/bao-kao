"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Bao hypervisor backend.
"""

from __future__ import annotations

import importlib
import sys
import os
from utils.process import run_cmd


CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, "../"))

if SRC_DIR not in sys.path:
    sys.path.append(
        SRC_DIR
        )


print_log = getattr(importlib.import_module("constants"), "print_log")
GenericHypervisor = getattr(
    importlib.import_module("generic"),
    "generic_hypervisor",
)

class Bao(GenericHypervisor):
    """Bao hypervisor integration."""

    def __init__(self, wrkdir):
        """Initialize Bao source and revision metadata."""
        super().__init__(wrkdir)
        self.git_repo = "https://github.com/bao-project/bao-hypervisor.git"
        self.git_rev = "v2.0.0"
        self.srcs_path = None

    def fetch_sources(self, hypervisor_srcs):
        """Fetch Bao sources or use the user-provided source tree."""
        if hypervisor_srcs == "":
            self.srcs_path = os.path.join(self.wrkdir, "hypervisor", "bao")
            self.clone_hypervisor(self.git_repo, self.git_rev, self.srcs_path)
            return

        self.srcs_path = hypervisor_srcs
        print_log(
            "INFO",
            f"Using provided hypervisor sources at {self.srcs_path}",
            tab_level=2,
        )

    def build(  # pylint: disable=too-many-arguments
        self,
        wrkdir_imgs,
        config_repo, config_name,
        platform,
        env,
    ):
        """Build Bao for the selected platform and configuration."""
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            f"CONFIG_REPO={config_repo}",
            f"CONFIG={config_name}",
            f"CPPFLAGS=-DBAO_WRKDIR_IMGS={wrkdir_imgs}",
        ]
        run_cmd(make_cmd, cwd=self.srcs_path, env=env)

        bin_name = "bao.bin"
        elf_name = "bao.elf"
        out_img = os.path.join(self.srcs_path, "bin", platform, platform, bin_name)
        return out_img, bin_name, elf_name

bao = Bao  # pylint: disable=invalid-name
