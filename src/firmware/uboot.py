"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
U-Boot firmware download, build, and configuration helpers.
"""

from __future__ import annotations

import os

from utils.process import run_command, setup_framework_path, get_print_log  # pylint: disable=import-error

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

setup_framework_path()
print_log = get_print_log()


class Uboot:
    """Build U-Boot firmware artifacts for supported platforms."""

    def __init__(self, firmware_dir):
        """Initialize source paths and supported platform mappings."""
        self.src_dir = os.path.join(firmware_dir, "uboot")
        self.git_repo = "https://github.com/u-boot/u-boot.git"
        self.uboot_version = "v2025.10"

        os.makedirs(self.src_dir, exist_ok=True)

        self.defconfig_map = {
            "qemu-aarch64-virt": "qemu_arm64_defconfig",
            "fvp-a": "vexpress_aemv8a_semi_defconfig",
            "fvp-a-aarch32": "vexpress_aemv8a_semi_defconfig",
            "zcu104": "xilinx_zynqmp_virt_defconfig",
        }

    def fetch_sources(self):
        """Clone the U-Boot sources if they are not already present."""
        if not os.listdir(self.src_dir):
            print_log("INFO", f"Cloning U-Boot {self.uboot_version}...", tab_level=2)
            run_command(
                ["git", "clone", "--branch", self.uboot_version, self.git_repo, self.src_dir]
            )
            return

        print_log("INFO", "U-Boot source already exists", tab_level=2)

    def build(self, platform, toolchain):
        """Build U-Boot for the selected platform."""
        if platform not in self.defconfig_map:
            raise ValueError(f"Unsupported platform: {platform}")

        defconfig = self.defconfig_map[platform]
        env = os.environ.copy()
        env["CROSS_COMPILE"] = toolchain

        self.fetch_sources()

        patch_path = os.path.join(CUR_DIR, "patches", platform, "u-boot.patch")
        if os.path.isfile(patch_path):
            print_log("INFO", f"Applying U-Boot patch: {patch_path}", tab_level=2)
            run_command(["git", "apply", patch_path], cwd=self.src_dir, env=env)

        print_log("INFO", f"Applying defconfig for {platform}: {defconfig}", tab_level=2)
        run_command(["make", defconfig], cwd=self.src_dir, env=env)

        frag_base = os.path.join(CUR_DIR, "configs", f"{platform}.cfg")
        frag_list = [frag_base] if os.path.isfile(frag_base) else []

        if frag_list:
            print_log("INFO", f"Merging U-Boot config fragment(s): {frag_list}", tab_level=2)
            run_command(
                ["bash", "scripts/kconfig/merge_config.sh", "-m", ".config", *frag_list],
                cwd=self.src_dir,
                env=env,
            )
            run_command(["make", "olddefconfig"], cwd=self.src_dir, env=env)

        print_log("INFO", f"Building U-Boot for platform {platform}...", tab_level=2)
        run_command(["make", f"-j{os.cpu_count()}"], cwd=self.src_dir, env=env)

        print_log("SUCCESS", f"U-Boot built successfully for {platform}.", tab_level=2)
        return os.path.join(self.src_dir, "u-boot.bin")


uboot = Uboot  # pylint: disable=invalid-name
