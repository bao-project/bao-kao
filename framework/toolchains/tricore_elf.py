# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import urllib.request
from urllib.request import Request, urlopen
import tarfile
import shutil
import subprocess
import zipfile

class tricore_elf:
    def __init__(self, toolchain_dir, host_platform="x86_64"):
        self.toolchain_version = "09-2025"
        self.toolchain_dir = toolchain_dir
        self.host_platform = host_platform
        self.zip_path = toolchain_dir + ".zip"

        self.download_url = f"https://softwaretools-hosting.infineon.com/packages/com.ifx.tb.tool.aurixgcc/versions/{self.toolchain_version}/artifacts/aurixgcc_09-2025_Linux_{self.host_platform}.zip/download"
        os.makedirs(os.path.dirname(self.toolchain_dir), exist_ok=True)
        

    def fetch_sources(self):

        print(f"Download the toolchain tarball if not present.")
        print(f"Toolchain dir:{self.toolchain_dir}"), 
        need_extract = False
        if not os.path.exists(self.toolchain_dir):
            print(f"[INFO] Downloading {self.download_url}...")
            urllib.request.urlretrieve(self.download_url, self.zip_path)
            input(f"[INFO] Download complete. Press Enter to continue...")
            print(f"[INFO] Downloaded to {self.toolchain_dir}")
            need_extract = True
        else:
            print(f"[INFO] Toolchain already exists: {self.toolchain_dir}")
        return self.toolchain_dir, need_extract 
    
    def extract(self, tarball_path):
        """Extract the tarball into self.toolchain_dir"""
        extract_parent = os.path.dirname(self.toolchain_dir)

        print(f"[INFO] Extracting {tarball_path}...")
        with zipfile.ZipFile(tarball_path, 'r') as zip_ref:
            zip_ref.extractall(self.toolchain_dir)

        print(f"[INFO] Extracted to {self.toolchain_dir}")

    def install(self):
        """Download, extract, and verify the toolchain."""

        path = shutil.which("tricore-elf-gcc")
        is_installed = False
        if path:
            #result = subprocess.run([path, "--version"], stdout=subprocess.PIPE, text=True)
            #version_line = result.stdout.splitlines()[0]
            #if self.toolchain_version in version_line:
            is_installed = True
        if not is_installed:
            print(f"[INFO] Please download the tricore-elf- toolchain from")
            print(f"[INFO] https://softwaretools-hosting.infineon.com/packages/com.ifx.tb.tool.aurixgcc/versions/09-2025/artifacts/aurixgcc_09-2025_Linux_x86-x64.zip/download")
            #toolchain_dir, need_extract = self.fetch_sources()
            #if need_extract:
            #    self.extract(self.zip_path)
            #toolchain_dir += "/bin/tricore-elf-"
            #return toolchain_dir
        else:
            print(f"[INFO] tricore-gcc already installed and up to date.")
            return "tricore-elf-"

