# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import subprocess
import shutil
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log


class opensbi:
    def __init__(self, firmware_dir):
        self.src_dir = f"{firmware_dir}/opensbi"
        self.git_repo = "https://github.com/bao-project/opensbi.git"
        self.git_rev = "4489876e933d8ba0d8bc6c64bae71e295d45faac"

        if not os.path.exists(self.src_dir):
            os.makedirs(self.src_dir)

        self.platform_map = {
            "qemu-riscv64-virt": "generic",
        }

    def run_command(self, command, cwd=None, env=None):
        result = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Command '{' '.join(command)}' failed")
            raise Exception(f"Command '{' '.join(command)}' failed")
        return result.returncode

    def fetch_sources(self):
        if not os.listdir(self.src_dir):
            print_log("INFO", "Cloning OpenSBI...", tab_level=2)
            self.run_command([
                "git", "clone", self.git_repo, self.src_dir
            ])
            self.run_command(["git", "checkout", self.git_rev], cwd=self.src_dir)
        else:
            print_log("INFO", "OpenSBI source already exists", tab_level=2)

    def build(self, platform, payload_bin, toolchain, fdt_addr="0x80100000"):
        if platform not in self.platform_map:
            raise ValueError(f"Unsupported platform: {platform}")

        opensbi_platform = self.platform_map[platform]
        env = os.environ.copy()
        env["CROSS_COMPILE"] = toolchain

        self.fetch_sources()

        print_log("INFO", f"Building OpenSBI for {platform}...", tab_level=2)
        self.run_command(
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
            self.src_dir,
            "build",
            "platform",
            opensbi_platform,
            "firmware",
            "fw_payload.elf",
        )

        if not os.path.isfile(fw_elf):
            raise FileNotFoundError(f"Expected OpenSBI firmware not found: {fw_elf}")

        print_log("SUCCESS", f"OpenSBI built successfully for {platform}.", tab_level=2)
        return fw_elf

    def install(self, platform, firmware_dir):
        if platform not in self.platform_map:
            raise ValueError(f"Unsupported platform: {platform}")

        opensbi_platform = self.platform_map[platform]
        src_elf = os.path.join(
            self.src_dir,
            "build",
            "platform",
            opensbi_platform,
            "firmware",
            "fw_payload.elf",
        )

        if not os.path.isfile(src_elf):
            raise FileNotFoundError(f"OpenSBI firmware not found: {src_elf}")

        dst_elf = os.path.join(firmware_dir, "opensbi.elf")
        shutil.copy(src_elf, dst_elf)

        print_log("SUCCESS", f"Installed OpenSBI to {dst_elf}", tab_level=2)
        return dst_elf