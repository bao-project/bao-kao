"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
ARM Trusted Firmware download, build, and installation helpers.
"""

from __future__ import annotations

import shutil
import os

from utils.process import run_command, setup_framework_path, get_print_log  # pylint: disable=import-error

setup_framework_path()
print_log = get_print_log()


class Atf:
    """Build and install ARM Trusted Firmware artifacts."""

    def __init__(self, firmware_dir):
        """Initialize source paths and supported platform mappings."""
        self.srcs_dir = os.path.join(firmware_dir, "atf")
        self.git_repo = "https://github.com/bao-project/arm-trusted-firmware.git"
        self.atf_version = "bao/demo"
        self.platform_dict = {
            "qemu-aarch64-virt": "qemu",
            "fvp-a": "fvp",
            "fvp-a-aarch32": "fvp",
        }

        os.makedirs(self.srcs_dir, exist_ok=True)

    def fetch_sources(self):
        """Clone the ATF sources and check out the configured revision."""
        if not os.path.exists(os.path.join(self.srcs_dir, ".git")):
            print_log("INFO", f"Cloning ATF from {self.git_repo}", tab_level=2)
            run_command(["git", "clone", self.git_repo, self.srcs_dir])

        print_log("INFO", f"Checking out ATF revision {self.atf_version}", tab_level=2)
        run_command(["git", "fetch", "--all"], cwd=self.srcs_dir)
        run_command(["git", "checkout", self.atf_version], cwd=self.srcs_dir)

    def build(self, platform, uboot_bin, toolchain, gic_version=None):
        """Build ATF for the selected platform."""
        self.fetch_sources()

        env = os.environ.copy()
        env["CROSS_COMPILE"] = toolchain
        env["ARCH"] = "aarch64"

        build_cmd = [
            "make",
            f"PLAT={self.platform_dict.get(platform, '')}",
            "bl1",
            "fip",
            f"BL33={uboot_bin}",
            f"QEMU_USE_GIC_DRIVER=QEMU_{gic_version}",
        ]

        print_log("INFO", f"Building ATF for {platform}...", tab_level=2)
        run_command(build_cmd, cwd=self.srcs_dir, env=env)

    def install(self, platform, out_dir):
        """Install built ATF artifacts into the output directory."""
        os.makedirs(out_dir, exist_ok=True)

        plat = self.platform_dict.get(platform, "")
        bl1_src = os.path.join(self.srcs_dir, f"build/{plat}/release/bl1.bin")
        fip_src = os.path.join(self.srcs_dir, f"build/{plat}/release/fip.bin")

        if platform == "qemu-aarch64-virt":
            flash_dst = os.path.join(out_dir, "flash.bin")
            run_command(["dd", f"if={bl1_src}", f"of={flash_dst}"], cwd=self.srcs_dir)
            run_command(
                ["dd", f"if={fip_src}", f"of={flash_dst}", "seek=64", "bs=4096", "conv=notrunc"],
                cwd=self.srcs_dir,
            )
        elif platform in ("fvp-a", "fvp-a-aarch32"):
            shutil.copy(bl1_src, out_dir)
            shutil.copy(fip_src, out_dir)
        else:
            raise ValueError(f"Unsupported platform for install: {platform}")

        print_log("SUCCESS", "ATF installed", tab_level=2)


atf = Atf  # pylint: disable=invalid-name
