"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Toolchain support for the TriCore ELF toolchain.
"""

import os
import urllib.request
import tarfile
import shutil
import subprocess
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log  # pylint: disable=wrong-import-position


class TricoreElf:
    """Helper class to manage the TriCore ELF toolchain installation and discovery."""
    def __init__(self, toolchain_dir, host_platform="x86_64"):
        self.toolchain_version = "09-2025"
        self.toolchain_dir = toolchain_dir
        self.toolchain_parent = os.path.dirname(self.toolchain_dir)

        # Map uname -m output to the release tarball naming convention
        platform_map = {
            "x86_64": "Linux_x86-64",
            "aarch64": "Linux_aarch64",
        }
        self.host_platform = platform_map.get(host_platform, host_platform)

        self.toolchain_prefix = os.path.join(self.toolchain_dir, "bin", "tricore-elf-")
        self.toolchain_gcc = f"{self.toolchain_prefix}gcc"

        tarball_name = f"aurixgcc_{self.toolchain_version}_{self.host_platform}.tar.xz"
        self.download_url = (
            f"https://github.com/bao-project/bao-tricore-toolchain/releases/download/"
            f"aurixgcc_{self.toolchain_version}_{self.host_platform}/{tarball_name}"
        )

        os.makedirs(self.toolchain_parent, exist_ok=True)

    def _resolve_local_prefix(self):
        """Check for the toolchain locally and set the prefix if found."""
        candidate_prefixes = [
            os.path.join(self.toolchain_dir, "bin", "tricore-elf-"),
            os.path.join(self.toolchain_parent, "bin", "tricore-elf-"),
        ]
        for prefix in candidate_prefixes:
            gcc_path = f"{prefix}gcc"
            if os.path.isfile(gcc_path):
                self.toolchain_prefix = prefix
                self.toolchain_gcc = gcc_path
                return prefix
        return None

    def fetch_sources(self):
        """Fetch the toolchain sources, either from a local path or by downloading the tarball."""
        need_extract = False
        tarball_path = f"{self.toolchain_dir}.tar.xz"

        if self._resolve_local_prefix():
            print_log("INFO", "Toolchain already exists locally", tab_level=3)
        else:
            if not os.path.exists(tarball_path):
                print_log("INFO", f"Downloading {self.download_url}...", tab_level=3)
                urllib.request.urlretrieve(self.download_url, tarball_path)
                print_log("INFO", f"Downloaded to {tarball_path}", tab_level=3)
            else:
                print_log("INFO", f"Tarball already exists locally: {tarball_path}", tab_level=3)
            need_extract = True

        return tarball_path, need_extract

    def extract(self, tarball_path):
        """Extract the downloaded tarball to the toolchain directory."""
        extract_parent = self.toolchain_parent

        print_log("INFO", f"Extracting {tarball_path} to {extract_parent}...", tab_level=3)

        with tarfile.open(tarball_path, "r:xz") as tar:
            top_level_names = set()
            for member_name in (member.name for member in tar.getmembers()):
                member_name = member_name.lstrip("./").lstrip("/")
                if not member_name:
                    continue

                root = member_name.split("/", 1)[0]
                if root and root != ".":
                    top_level_names.add(root)

            top_level_dir = next(iter(top_level_names), None) \
                if len(top_level_names) == 1 else None

            tar.extractall(path=extract_parent)

        if os.path.exists(tarball_path):
            os.remove(tarball_path)

        if top_level_dir:
            extracted_folder = os.path.join(
                extract_parent, top_level_dir
                )
            if extracted_folder != self.toolchain_dir and os.path.isdir(extracted_folder):
                if os.path.exists(self.toolchain_dir):
                    shutil.rmtree(self.toolchain_dir)
                os.rename(extracted_folder, self.toolchain_dir)
        else:
            print_log("WARNING", "No single top-level directory found in tarball", tab_level=3)

        if not self._resolve_local_prefix():
            raise RuntimeError(
                "TriCore toolchain install failed after extraction: "
                f"missing compiler at {self.toolchain_gcc}"
            )

        print_log("INFO", f"Extracted to {self.toolchain_dir}", tab_level=3)

    def install(self):
        """Install the toolchain."""
        path = shutil.which("tricore-elf-gcc")
        is_installed = False

        if path:
            result = subprocess.run(
                [path, "--version"], stdout=subprocess.PIPE, text=True, check=False
                )
            if result.returncode == 0 and result.stdout:
                is_installed = True

        if not is_installed:
            tarball_path, need_extract = self.fetch_sources()
            if need_extract:
                self.extract(
                    tarball_path
                )
            if not self._resolve_local_prefix():
                raise RuntimeError(
                    "TriCore toolchain install failed: missing compiler at "
                    f"{self.toolchain_gcc}"
                )
            return self.toolchain_prefix

        print_log("INFO", "tricore-elf-gcc already installed.", tab_level=3)
        return "tricore-elf-"

tricore_elf = TricoreElf  # pylint: disable=invalid-name
