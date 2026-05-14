"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
TriCore ELF toolchain download, extraction, and discovery helpers.
"""

# pylint: disable=duplicate-code
from __future__ import annotations

# pylint: disable=duplicate-code
import os
# pylint: disable=duplicate-code
import shutil
# pylint: disable=duplicate-code
import urllib.request
# pylint: disable=duplicate-code
import zipfile


# pylint: disable=duplicate-code
from utils.process import setup_framework_path, get_print_log  # pylint: disable=import-error

setup_framework_path()
print_log = get_print_log()
class TricoreElf:
    """Manage installation and discovery of the TriCore ELF toolchain."""

    def __init__(self, toolchain_dir, host_platform="x86_64"):
        """Initialize toolchain paths and download metadata."""
        self.toolchain_version = "09-2025"
        self.toolchain_dir = toolchain_dir
        self.host_platform = host_platform
        self.zip_path = f"{toolchain_dir}.zip"
        self.toolchain_prefix = os.path.join(
            self.toolchain_dir,
            "bin",
            "tricore-elf-",
        )

        self.download_url = (
            "https://softwaretools-hosting.infineon.com/packages/"
            "com.ifx.tb.tool.aurixgcc/versions/"
            f"{self.toolchain_version}/artifacts/"
            f"aurixgcc_09-2025_Linux_{self.host_platform}.zip/download"
        )

        os.makedirs(os.path.dirname(self.toolchain_dir), exist_ok=True)

    def fetch_sources(self):
        """Download the toolchain archive if it is not already present."""
        need_extract = False

        print_log("INFO", "Download the toolchain zip if not present.", tab_level=3)
        print_log("INFO", f"Toolchain dir: {self.toolchain_dir}", tab_level=3)

        if not os.path.exists(self.toolchain_dir):
            if not os.path.exists(self.zip_path):
                print_log("INFO", f"Downloading {self.download_url}...", tab_level=3)
                urllib.request.urlretrieve(self.download_url, self.zip_path)
                print_log("INFO", "Download complete.", tab_level=3)
                print_log("INFO", f"Downloaded to {self.zip_path}", tab_level=3)
            else:
                print_log(
                    "INFO",
                    f"Archive already exists: {self.zip_path}",
                    tab_level=3,
                )
            need_extract = True
        else:
            print_log(
                "INFO",
                f"Toolchain already exists: {self.toolchain_dir}",
                tab_level=3,
            )

        return self.zip_path, need_extract

    def extract(self, archive_path):
        """Extract the downloaded zip archive into the toolchain directory."""
        print_log("INFO", f"Extracting {archive_path}...", tab_level=3)

        if os.path.exists(self.toolchain_dir):
            shutil.rmtree(self.toolchain_dir)

        os.makedirs(self.toolchain_dir, exist_ok=True)
        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            zip_ref.extractall(self.toolchain_dir)

        print_log("INFO", f"Extracted to {self.toolchain_dir}", tab_level=3)

    def install(self):
        """Install the toolchain locally or return the system compiler prefix."""
        compiler_path = shutil.which("tricore-elf-gcc")
        if compiler_path:
            print_log(
                "INFO",
                "tricore-elf-gcc already installed and up to date.",
                tab_level=3,
            )
            return "tricore-elf-"

        archive_path, need_extract = self.fetch_sources()
        if need_extract:
            self.extract(archive_path)

        local_gcc = f"{self.toolchain_prefix}gcc"
        if os.path.isfile(local_gcc):
            return self.toolchain_prefix

        print_log("INFO", "Please download the tricore-elf toolchain from:", tab_level=3)
        print_log("INFO", self.download_url, tab_level=3)
        return None


tricore_elf = TricoreElf  # pylint: disable=invalid-name
