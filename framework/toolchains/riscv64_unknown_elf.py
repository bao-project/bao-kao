# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import urllib.request
import tarfile
import shutil
import subprocess
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log


class riscv64_unknown_elf:
    def __init__(self, toolchain_dir, host_platform="x86_64"):
        self.toolchain_version = "gc891d8dc23e"
        self.toolchain_dir = toolchain_dir
        self.host_platform = host_platform

        tarball_name = "riscv64-unknown-elf.tar.gz"
        self.download_url = (
            f"https://github.com/bao-project/bao-riscv-toolchain/releases/download/"
            f"{self.toolchain_version}/{tarball_name}"
        )

        os.makedirs(os.path.dirname(self.toolchain_dir), exist_ok=True)

    def fetch_sources(self):
        need_extract = False
        tarball_path = f"{self.toolchain_dir}.tar.gz"

        if not os.path.exists(self.toolchain_dir):
            if not os.path.exists(tarball_path):
                print_log("INFO", f"Downloading {self.download_url}...", tab_level=3)
                urllib.request.urlretrieve(self.download_url, tarball_path)
                print_log("INFO", f"Downloaded to {tarball_path}", tab_level=3)
            else:
                print_log("INFO", f"Tarball already exists locally: {tarball_path}", tab_level=3)

            need_extract = True
        else:
            print_log("INFO", "Toolchain already exists locally", tab_level=3)

        return tarball_path, need_extract

    def extract(self, tarball_path):
        extract_parent = os.path.dirname(self.toolchain_dir)

        print_log("INFO", f"Extracting {tarball_path} to {extract_parent}...", tab_level=3)
        
        # Find the common top-level directory in the tarball
        with tarfile.open(tarball_path, "r:gz") as tar:
            # Get all top-level names (first component of each path)
            top_level_names = set()
            for member in tar.getmembers():
                # Get the first component of the path
                parts = member.name.split('/')
                if parts[0] and parts[0] != '.':
                    top_level_names.add(parts[0])
            
            # If there's exactly one top-level directory, use it
            if len(top_level_names) == 1:
                top_level_dir = list(top_level_names)[0]
            else:
                # Multiple top-level entries or none - extract directly
                top_level_dir = None
            
            # Extract to parent directory
            tar.extractall(path=extract_parent)

        # Delete the tarball after extraction
        if os.path.exists(tarball_path):
            os.remove(tarball_path)

        # If there's a single top-level directory, rename it to the target
        if top_level_dir:
            extracted_folder = os.path.join(extract_parent, top_level_dir)
            if extracted_folder != self.toolchain_dir:
                if os.path.exists(self.toolchain_dir):
                    shutil.rmtree(self.toolchain_dir)
                os.rename(extracted_folder, self.toolchain_dir)
        else:
            # Files were extracted directly to extract_parent, no rename needed
            # This shouldn't happen with properly structured toolchain tarballs
            print_log("WARNING", f"No single top-level directory found in tarball", tab_level=3)

        print_log("INFO", f"Extracted to {self.toolchain_dir}", tab_level=3)

    def install(self):
        path = shutil.which("riscv64-unknown-elf-gcc")
        is_installed = False

        if path:
            result = subprocess.run([path, "--version"], stdout=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout:
                is_installed = True

        if not is_installed:
            tarball_path, need_extract = self.fetch_sources()
            if need_extract:
                self.extract(tarball_path)
            return os.path.join(self.toolchain_dir, "bin", "riscv64-unknown-elf-")
        else:
            print_log("INFO", "riscv64-unknown-elf-gcc already installed.", tab_level=3)
            return "riscv64-unknown-elf-"