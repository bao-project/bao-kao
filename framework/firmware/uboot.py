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
        self.uboot_version = "v2025.10"
        
        if not os.path.exists(self.src_dir):
            os.makedirs(self.src_dir)

        self.defconfig_map = {
            "qemu-aarch64-virt":    "qemu_arm64_defconfig",
            "fvp-a":                "vexpress_aemv8a_semi_defconfig",
            "fvp-a-aarch32":        "vexpress_aemv8a_semi_defconfig",
            "zcu104":               "xilinx_zynqmp_virt_defconfig",
        }

    def run_command(self, command, cwd=None, env=None):
        # result = subprocess.run(command, cwd=cwd, env=env,
        #                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # run command with verbose output
        result = subprocess.run(command, cwd=cwd, env=env)
        if result.returncode != 0:
            print(f"[ERROR] Command '{' '.join(command)}' failed:\n{result.stderr}")
            raise Exception(f"Command '{' '.join(command)}' failed")
        return result.stdout

    def fetch_sources(self):
        if not os.listdir(self.src_dir):
            print_log("INFO", f"Cloning U-Boot {self.uboot_version}...", tab_level=2)
            self.run_command([
                "git", "clone", "--branch", f"{self.uboot_version}", self.git_repo, self.src_dir
            ])
        else:
            print_log("INFO", f"U-Boot source already exists", tab_level=2)

    # def build(self, platform, toolchain, boot_cmd=None):
    #     if platform not in self.defconfig_map:
    #         raise ValueError(f"Unsupported platform: {platform}")

    #     defconfig = self.defconfig_map[platform]
    #     env = os.environ.copy()
    #     env["CROSS_COMPILE"] = toolchain

    #     self.fetch_sources()

    #     print_log("INFO", f"Applying defconfig for platform {platform}: {defconfig}", tab_level=2)
    #     self.run_command(["make", defconfig], cwd=self.src_dir, env=env)
        
    #     config_file = os.path.join(self.src_dir, ".config")
    #     with open(config_file, "a") as f:
    #         f.write("CONFIG_TFABOOT=y\n")
    #         f.write("CONFIG_SYS_TEXT_BASE=0x60000000\n")
    #         f.write("CONFIG_CMD_WGET=y\n")
    #         f.write("CONFIG_BOOTDELAY=0\n")
    #         if boot_cmd:
    #             f.write(f"CONFIG_BOOTCOMMAND=\"{boot_cmd}\"\n")
    #         else:
    #             f.write("CONFIG_BOOTCOMMAND=\"go 0x50000000\"\n")

    #     print_log("INFO", f"Building U-Boot for platform {platform}...", tab_level=2)
    #     self.run_command(["make", f"-j{os.cpu_count()}"], cwd=self.src_dir, env=env)

    #     # Install phase: copy u-boot.bin to bin directory
    #     print_log("SUCCESS", f"U-Boot built successfully for {platform}.", tab_level=2)
    #     uboot_bin = os.path.join(self.src_dir, "u-boot.bin")
    #     return uboot_bin


    def build(self, platform, toolchain):
        if platform not in self.defconfig_map:
            raise ValueError(f"Unsupported platform: {platform}")

        defconfig = self.defconfig_map[platform]
        env = os.environ.copy()
        env["CROSS_COMPILE"] = toolchain

        self.fetch_sources()

        patch_path = os.path.join(cur_dir, "patches", platform, "u-boot.patch")
        if os.path.isfile(patch_path):
            print_log("INFO", f"Applying U-Boot patch: {patch_path}", tab_level=2)
            self.run_command(["git", "apply", patch_path], cwd=self.src_dir, env=env)

        print_log("INFO", f"Applying defconfig for {platform}: {defconfig}", tab_level=2)
        self.run_command(["make", defconfig], cwd=self.src_dir, env=env)

        frag_base = os.path.join(cur_dir, "configs", f"{platform}.cfg")
        frag_list = []
        if os.path.isfile(frag_base):
            frag_list.append(frag_base)

        if frag_list:
            print_log("INFO", f"Merging U-Boot config fragment(s): {frag_list}", tab_level=2)
            self.run_command(
                ["bash", "scripts/kconfig/merge_config.sh", "-m", ".config", *frag_list],
                cwd=self.src_dir, env=env
            )  # merge_config.sh merges fragments and writes .config [web:525]
            self.run_command(["make", "olddefconfig"], cwd=self.src_dir, env=env)

        # 4) Build
        print_log("INFO", f"Building U-Boot for platform {platform}...", tab_level=2)
        self.run_command(["make", f"-j{os.cpu_count()}"], cwd=self.src_dir, env=env)

        print_log("SUCCESS", f"U-Boot built successfully for {platform}.", tab_level=2)
        return os.path.join(self.src_dir, "u-boot.bin")


    # def build(self, platform, toolchain, boot_cmd=None):
    #     if platform not in self.defconfig_map:
    #         raise ValueError(f"Unsupported platform: {platform}")

    #     defconfig = self.defconfig_map[platform]
    #     env = os.environ.copy()
    #     env["CROSS_COMPILE"] = toolchain

    #     self.fetch_sources()

    #     print_log("INFO", f"Applying defconfig for platform {platform}: {defconfig}", tab_level=2)
    #     self.run_command(["make", defconfig], cwd=self.src_dir, env=env)

    #     cfg = ["./scripts/config", "--file", ".config"]

    #     self.run_command(cfg + ["-e", "TFABOOT"], cwd=self.src_dir, env=env)
    #     self.run_command(cfg + ["--set-val", "SYS_TEXT_BASE", "0x60000000"], cwd=self.src_dir, env=env)
    #     self.run_command(cfg + ["--set-val", "BOOTDELAY", "0"], cwd=self.src_dir, env=env)

    #     self.run_command(cfg + ["-e", "CMD_WGET"], cwd=self.src_dir, env=env)


    #     if boot_cmd:
    #         self.run_command(cfg + ["-e", "USE_BOOTCOMMAND"], cwd=self.src_dir, env=env)
    #         self.run_command(cfg + ["--set-str", "BOOTCOMMAND", boot_cmd], cwd=self.src_dir, env=env)
    #     else:
    #         self.run_command(cfg + ["-e", "USE_BOOTCOMMAND"], cwd=self.src_dir, env=env)
    #         self.run_command(cfg + ["--set-str", "BOOTCOMMAND", "go 0x50000000"], cwd=self.src_dir, env=env)

    #     self.run_command(["make", "olddefconfig"], cwd=self.src_dir, env=env)

    #     print_log("INFO", f"Building U-Boot for platform {platform}...", tab_level=2)
    #     self.run_command(["make", f"-j{os.cpu_count()}"], cwd=self.src_dir, env=env)

    #     print_log("SUCCESS", f"U-Boot built successfully for {platform}.", tab_level=2)
    #     uboot_bin = os.path.join(self.src_dir, "u-boot.bin")
    #     return uboot_bin



# class xilinx_uboot(uboot):
#     def __init__(self, firmware_dir):
#         super().__init__(firmware_dir)
#         self.src_dir = f"{firmware_dir}/uboot-xlnx"
#         self.git_repo = "https://github.com/Xilinx/u-boot-xlnx.git"
#         self.uboot_version = "xlnx_rebase_v2025.10"

#         if not os.path.exists(self.src_dir):
#             os.makedirs(self.src_dir)
