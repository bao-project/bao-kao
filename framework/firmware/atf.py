# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.
import os
import subprocess
import shutil

class atf:
    def __init__(self, firmware_dir):
        self.srcs_dir = f"{firmware_dir}/atf"
        self.git_repo = "https://github.com/bao-project/arm-trusted-firmware.git"
        self.atf_version = "bao/demo"
        self.platform_dict = {
            "qemu-aarch64-virt": "qemu",
            "fvp-a": "fvp",
            "fvp-a-aarch32": "fvp",
        }

        if not os.path.exists(self.srcs_dir):
            os.makedirs(self.srcs_dir)
    
    def run_command(self, command, cwd=None):
        """Run a shell command and raise on error."""
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"[ERROR] Command '{' '.join(command)}' failed:\n{result.stderr}")
            raise Exception(f"Command '{' '.join(command)}' failed")
        return result.stdout
    
    def fetch_sources(self):
        if not os.path.exists(os.path.join(self.srcs_dir, ".git")):
            print(f"[INFO] Cloning ATF from {self.git_repo}")
            self.run_command([
                "git", "clone", self.git_repo, self.srcs_dir
            ])

        print(f"[INFO] Checking out ATF revision {self.atf_version}")
        self.run_command(["git", "fetch", "--all"],
                         cwd=self.srcs_dir)
        self.run_command(["git", "checkout", self.atf_version],
                         cwd=self.srcs_dir)

    def build(self, platform, uboot_bin, toolchain, gic_version=None):
        self.fetch_sources()
        os.environ["CROSS_COMPILE"] = toolchain
        os.environ["ARCH"] = "aarch64"

        build_cmd = [
            "make",
            f"PLAT={self.platform_dict.get(platform, '')}",
            "bl1",
            "fip",
            f"BL33={uboot_bin}",
            f"QEMU_USE_GIC_DRIVER=QEMU_{gic_version}",
            # f"ARCH=aarch64"
        ]

        print(f"[INFO] Building ATF for {platform}...")
        print("[CMD] " + " ".join(build_cmd))
        self.run_command(build_cmd, cwd=self.srcs_dir)

    def install(self, platform, out_dir):
        target_dir = os.path.join(out_dir)
        os.makedirs(target_dir, exist_ok=True)

        bl1_src = os.path.join(
            self.srcs_dir,
            f"build/{self.platform_dict.get(platform, '')}/release/bl1.bin",
        )
        fip_src = os.path.join(
            self.srcs_dir,
            f"build/{self.platform_dict.get(platform, '')}/release/fip.bin",
        )

        if platform == "qemu-aarch64-virt":
            flash_dst = os.path.join(target_dir, "flash.bin")

            # dd if=bl1.bin of=flash.bin
            subprocess.run(
                ["dd", f"if={bl1_src}", f"of={flash_dst}"], check=True
            )

            subprocess.run(
                [   "dd", f"if={fip_src}", f"of={flash_dst}",
                    "seek=64", "bs=4096", "conv=notrunc",
                ], check=True
            )

        elif platform in ["fvp-a", "fvp-a-aarch32"]:
            shutil.copy(bl1_src, target_dir)
            shutil.copy(fip_src, target_dir)

        else:
            raise ValueError(f"Unsupported platform for install: {platform}")

        print(f"[INFO] ATF installed to {target_dir}")
