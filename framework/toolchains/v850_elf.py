# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors.

import os
import shutil
import subprocess

class v850_elf:
    def __init__(self, toolchain_dir, host_platform="x86_64"):
        # Keep same interface even if host_platform is unused
        self.toolchain_dir = toolchain_dir
        self.host_platform = host_platform

        self.repo_url = "https://github.com/miguelafsilva5/bao-rh850-toolchain.git"
        self.repo_dir = self.toolchain_dir
        self.install_dir = os.path.join(self.repo_dir, "gcc-v850-elf-master")
        self.build_script = os.path.join(
            self.repo_dir, "build-gcc-v850-elf-toolchain.sh"
        )

        os.makedirs(os.path.dirname(self.toolchain_dir), exist_ok=True)

    def fetch_sources(self):
        """
        Clone the toolchain repo if not present.
        Returns (toolchain_dir, need_extract) to match arm_none_eabi.
        """
        need_extract = False

        if not os.path.exists(self.repo_dir):
            print(f"[INFO] Cloning {self.repo_url}...")
            subprocess.check_call([
                "git", "clone", self.repo_url, self.repo_dir
            ])
            need_extract = True
        else:
            print(f"[INFO] Toolchain repo already exists: {self.repo_dir}")

        return self.repo_dir, need_extract

    def extract(self, _unused_path):
        """
        Kept for interface compatibility.
        For this toolchain, 'extract' means running the build script.
        """
        if os.path.exists(self.install_dir):
            print("[INFO] Toolchain already built, skipping build.")
            return

        if not os.path.exists(self.build_script):
            raise FileNotFoundError(
                f"Build script not found: {self.build_script}"
            )

        print("[INFO] Building v850-elf toolchain...")
        subprocess.check_call(
            ["bash", self.build_script],
            cwd=self.repo_dir
        )

    def install(self):
        """
        Clone, build, and return the toolchain prefix.
        Matches arm_none_eabi.install() behavior.
        """
        path = shutil.which("v850-elf-gcc")
        is_installed = False

        if path:
            result = subprocess.run(
                [path, "--version"],
                stdout=subprocess.PIPE,
                text=True
            )
            if "v850" in result.stdout.lower():
                is_installed = True

        if not is_installed:
            toolchain_dir, need_extract = self.fetch_sources()
            if need_extract:
                self.extract(toolchain_dir)

            toolchain_prefix = os.path.join(
                self.install_dir, "bin", "v850-elf-"
            )
            return toolchain_prefix
        else:
            print("[INFO] v850-elf-gcc already installed.")
            return "v850-elf-"
