# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import subprocess
import shutil
import urllib.request
import tarfile
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

class uboot:
    def __init__(self, firmware_dir):

        self.src_dir = f"{firmware_dir}/uboot"
        self.git_repo = "https://github.com/u-boot/u-boot.git"
        self.uboot_version = "2022.10"
        
        if not os.path.exists(self.src_dir):
            os.makedirs(self.src_dir)

        self.defconfig_map = {
            "qemu-aarch64-virt":    "qemu_arm64_defconfig",
            "fvp-a":                "vexpress_aemv8a_semi_defconfig",
            "fvp-a-aarch32":        "vexpress_aemv8a_semi_defconfig",
        }

    def run_command(self, command, cwd=None, env=None):
        result = subprocess.run(command, cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Command '{' '.join(command)}' failed:\n{result.stderr}")
            raise Exception(f"Command '{' '.join(command)}' failed")
        return result.stdout

    def fetch_sources(self):
        if not os.listdir(self.src_dir):
            print_log("INFO", f"Cloning U-Boot {self.uboot_version}...", tab_level=2)
            self.run_command([
                "git", "clone", "--branch", f"v{self.uboot_version}", self.git_repo, self.src_dir
            ])
        else:
            print_log("INFO", f"U-Boot source already exists", tab_level=2)

    def build(self, platform, toolchain):
        if platform not in self.defconfig_map:
            raise ValueError(f"Unsupported platform: {platform}")

        defconfig = self.defconfig_map[platform]
        env = os.environ.copy()
        env["CROSS_COMPILE"] = toolchain

        self.fetch_sources()

        print_log("INFO", f"Applying defconfig for platform {platform}: {defconfig}", tab_level=2)
        self.run_command(["make", defconfig], cwd=self.src_dir, env=env)

        # Append required configs to .config
        config_file = os.path.join(self.src_dir, ".config")
        with open(config_file, "a") as f:
            f.write("CONFIG_TFABOOT=y\n")
            f.write("CONFIG_SYS_TEXT_BASE=0x60000000\n")
            f.write("CONFIG_BOOTDELAY=0\n")
            f.write("CONFIG_BOOTCOMMAND=\"go 0x50000000\"\n")

        print_log("INFO", f"Building U-Boot for platform {platform}...", tab_level=2)
        self.run_command(["make", f"-j{os.cpu_count()}"], cwd=self.src_dir, env=env)

        # Install phase: copy u-boot.bin to bin directory
        print_log("SUCCESS", f"U-Boot built successfully for {platform}.", tab_level=2)
        uboot_bin = os.path.join(self.src_dir, "u-boot.bin")
        return uboot_bin
