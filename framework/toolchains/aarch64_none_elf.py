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


class aarch64_none_elf:
    def __init__(self, toolchain_dir, host_platform="x86_64"):
        self.toolchain_version = "14.2.rel1"
        self.toolchain_dir = toolchain_dir
        self.host_platform = host_platform

        tarball_name = f"arm-gnu-toolchain-{self.toolchain_version}-{self.host_platform}-aarch64-none-elf.tar.xz"
        self.download_url = f"https://developer.arm.com/-/media/Files/downloads/gnu/{self.toolchain_version}/binrel/{tarball_name}"
        
        os.makedirs(os.path.dirname(self.toolchain_dir), exist_ok=True)
        

    def fetch_sources(self):
        """Download the toolchain tarball if not present."""
        need_extract = False
        if not os.path.exists(self.toolchain_dir):
            print_log("INFO", f"Downloading {self.download_url}...", tab_level=3)
            urllib.request.urlretrieve(self.download_url, self.toolchain_dir)
            input(f"[INFO] Download complete. Press Enter to continue...")
            print_log("INFO", f"Downloaded to {self.toolchain_dir}", tab_level=3)
            need_extract = True
        else:
            print_log("INFO", f"Toolchain already exists locally", tab_level=3)
        return self.toolchain_dir, need_extract 
    
    def extract(self, tarball_path):
        """Extract the tarball into self.toolchain_dir"""
        extract_parent = os.path.dirname(self.toolchain_dir)

        # if extract_parent exist, just skip extraction
        # if os.path.exists(self.toolchain_dir):
        #     print(f"[INFO] Toolchain directory already exists: {self.toolchain_dir}")
        #     return

        print_log("INFO", f"Extracting {tarball_path} to {extract_parent}...", tab_level=3)
        with tarfile.open(tarball_path, "r:xz") as tar:
            tar.extractall(path=extract_parent)
            top_dirs = [m.name.split("/")[0] for m in tar.getmembers() if m.isdir()]
            top_level_dir = os.path.commonprefix(top_dirs)

        extracted_folder = os.path.join(extract_parent, top_level_dir)

        # rename to self.toolchain_dir
        if os.path.exists(self.toolchain_dir):
            if os.path.isfile(self.toolchain_dir):
                os.remove(self.toolchain_dir)
            else:
                shutil.rmtree(self.toolchain_dir)
        os.rename(extracted_folder, self.toolchain_dir)
        print_log("INFO", f"Extracted to {self.toolchain_dir}", tab_level=3)

    def install(self):
        """Download, extract, and verify the toolchain."""

        path = shutil.which("aarch64-none-elf-gcc")
        is_installed = False
        if path:
            result = subprocess.run([path, "--version"], stdout=subprocess.PIPE, text=True)
            version_line = result.stdout.splitlines()[0]
            if self.toolchain_version in version_line:
                is_installed = True
        if not is_installed:
            toolchain_dir, need_extract = self.fetch_sources()
            if need_extract:
                self.extract(toolchain_dir)
            toolchain_dir += "/bin/aarch64-none-elf-"
            return toolchain_dir
        else:
            print_log("INFO", f"aarch64-none-elf-gcc already installed and up to date.", tab_level=3)
            return "aarch64-none-elf-"


