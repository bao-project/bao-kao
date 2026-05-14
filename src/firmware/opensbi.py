"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
OpenSBI firmware download, build, and installation helpers.
"""

from __future__ import annotations

import os
import shutil

from utils.process import run_command, setup_framework_path, get_print_log  # pylint: disable=import-error

setup_framework_path()
print_log = get_print_log()


class Opensbi:
    """Build and install OpenSBI firmware artifacts."""

    def __init__(self, firmware_dir):
        """Initialize source paths and supported platform mappings."""
        self.src_dir = os.path.join(firmware_dir, "opensbi")
        self.git_repo = "https://github.com/bao-project/opensbi.git"
        self.git_rev = "4489876e933d8ba0d8bc6c64bae71e295d45faac"

        os.makedirs(self.src_dir, exist_ok=True)

        self.platform_map = {
            "qemu-riscv64-virt": "generic",
        }

    def fetch_sources(self):
        """Clone the OpenSBI sources if they are not already present."""
        if not os.listdir(self.src_dir):
            print_log("INFO", "Cloning OpenSBI...", tab_level=2)
            run_command(["git", "clone", self.git_repo, self.src_dir])
            run_command(["git", "checkout", self.git_rev], cwd=self.src_dir)
            return

        print_log("INFO", "OpenSBI source already exists", tab_level=2)

    def build(self, platform, payload_bin, toolchain, fdt_addr="0x80100000"):
        """Build OpenSBI for the selected platform and payload."""
        if platform not in self.platform_map:
            raise ValueError(f"Unsupported platform: {platform}")

        opensbi_platform = self.platform_map[platform]
        env = os.environ.copy()
        env["CROSS_COMPILE"] = toolchain

        self.fetch_sources()

        print_log("INFO", f"Building OpenSBI for {platform}...", tab_level=2)
        run_command(
            [
                "make",
                f"PLATFORM={opensbi_platform}",
                "FW_PAYLOAD=y",
                f"FW_PAYLOAD_FDT_ADDR={fdt_addr}",
                f"FW_PAYLOAD_PATH={payload_bin}",
                f"-j{os.cpu_count()}",
            ],
            cwd=self.src_dir,
            env=env,
        )

        fw_elf = os.path.join(
            self.src_dir, "build", "platform", opensbi_platform, "firmware", "fw_payload.elf"
        )

        if not os.path.isfile(fw_elf):
            raise FileNotFoundError(f"Expected OpenSBI firmware not found: {fw_elf}")

        print_log("SUCCESS", f"OpenSBI built successfully for {platform}.", tab_level=2)
        return fw_elf

    def install(self, platform, firmware_dir):
        """Install the built OpenSBI firmware into the target firmware directory."""
        if platform not in self.platform_map:
            raise ValueError(f"Unsupported platform: {platform}")

        opensbi_platform = self.platform_map[platform]
        src_elf = os.path.join(
            self.src_dir, "build", "platform", opensbi_platform, "firmware", "fw_payload.elf"
        )

        if not os.path.isfile(src_elf):
            raise FileNotFoundError(f"OpenSBI firmware not found: {src_elf}")

        dst_elf = os.path.join(firmware_dir, "opensbi.elf")
        shutil.copy(src_elf, dst_elf)

        print_log("SUCCESS", f"Installed OpenSBI to {dst_elf}", tab_level=2)
        return dst_elf


opensbi = Opensbi  # pylint: disable=invalid-name
