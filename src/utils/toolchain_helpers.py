# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.
"""Shared helpers for tarball-based toolchain download and extraction."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import urllib.request

from utils.process import setup_framework_path, get_print_log  # pylint: disable=import-error

setup_framework_path()
print_log = get_print_log()


# ── Low-level helpers ────────────────────────────────────────────────────────

def fetch_tarball(download_url, tarball_path, print_log_fn):
    """Download *download_url* to *tarball_path* if not already present.

    Returns ``True`` when the archive needs to be extracted.
    """
    if not os.path.exists(tarball_path):
        print_log_fn("INFO", f"Downloading {download_url}...", tab_level=3)
        urllib.request.urlretrieve(download_url, tarball_path)
        print_log_fn("INFO", f"Downloaded to {tarball_path}", tab_level=3)
        return True

    print_log_fn("INFO", f"Tarball already exists locally: {tarball_path}", tab_level=3)
    return True


def extract_tarball(tarball_path, extract_parent, toolchain_dir, print_log_fn):
    """Extract *tarball_path* into *extract_parent* and rename to *toolchain_dir*."""
    print_log_fn(
        "INFO",
        f"Extracting {tarball_path} to {extract_parent}...",
        tab_level=3,
    )

    with tarfile.open(tarball_path, "r:gz") as tar:
        top_level_names = set()

        for member in tar.getmembers():
            member_name = member.name
            while member_name.startswith("./"):
                member_name = member_name[2:]
            member_name = member_name.lstrip("/")
            if not member_name:
                continue
            parts = member_name.split("/")
            if parts[0] and parts[0] != ".":
                top_level_names.add(parts[0])

        top_level_dir = list(top_level_names)[0] if len(top_level_names) == 1 else None
        tar.extractall(path=extract_parent)

    if os.path.exists(tarball_path):
        os.remove(tarball_path)

    if top_level_dir:
        extracted_folder = os.path.join(extract_parent, top_level_dir)
        if extracted_folder != toolchain_dir and os.path.isdir(extracted_folder):
            if os.path.exists(toolchain_dir):
                shutil.rmtree(toolchain_dir)
            os.rename(extracted_folder, toolchain_dir)
    else:
        print_log_fn("WARNING", "No single top-level directory found in tarball", tab_level=3)


def resolve_local_prefix(candidate_prefixes):
    """Return the first candidate prefix whose *gcc* binary exists, or ``None``."""
    for prefix in candidate_prefixes:
        if os.path.isfile(f"{prefix}gcc"):
            return prefix
    return None


def check_system_gcc(gcc_name, version_substr=None):
    """Return ``True`` if *gcc_name* is on PATH and optionally matches *version_substr*."""
    gcc_path = shutil.which(gcc_name)
    if not gcc_path:
        return False

    result = subprocess.run(
        [gcc_path, "--version"],
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return False

    if version_substr and version_substr not in result.stdout:
        return False

    return True


# ── ARM GNU toolchain base class ─────────────────────────────────────────────

class ArmGnuToolchainBase:
    """Base class for ARM developer toolchains distributed as .tar.xz archives.

    Subclasses must define:
        _GCC_NAME      – e.g. "aarch64-none-elf-gcc"
        _PREFIX_SUFFIX – e.g. "aarch64-none-elf-"
        _TRIPLE_TAG    – the triple part of the tarball name,
                         e.g. "aarch64-none-elf"
        _VERSION_CHECK – optional substring to verify version line; ``None``
                         accepts any version.
    """

    _GCC_NAME: str = ""
    _PREFIX_SUFFIX: str = ""
    _TRIPLE_TAG: str = ""
    _VERSION_CHECK: str | None = None

    _ARM_BASE_URL = "https://developer.arm.com/-/media/Files/downloads/gnu"

    def __init__(self, toolchain_dir, host_platform="x86_64"):
        """Initialize toolchain paths and download metadata."""
        self.toolchain_version = "14.2.rel1"
        self.toolchain_dir = toolchain_dir
        self.host_platform = host_platform

        tarball_name = (
            f"arm-gnu-toolchain-{self.toolchain_version}-"
            f"{self.host_platform}-{self._TRIPLE_TAG}.tar.xz"
        )
        self.tarball_name = tarball_name
        self.download_url = (
            f"{self._ARM_BASE_URL}/{self.toolchain_version}/binrel/{tarball_name}"
        )

        os.makedirs(os.path.dirname(self.toolchain_dir), exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_sources(self):
        """Download the toolchain tarball if it is not already present."""
        need_extract = False

        if not os.path.exists(self.toolchain_dir):
            print_log("INFO", f"Downloading {self.download_url}...", tab_level=3)
            urllib.request.urlretrieve(self.download_url, self.toolchain_dir)
            print_log("INFO", f"Downloaded to {self.toolchain_dir}", tab_level=3)
            need_extract = True
        else:
            print_log(
                "INFO", f"Toolchain already exists: {self.toolchain_dir}",
                tab_level=3,
            )

        return self.toolchain_dir, need_extract

    def _extract(self, tarball_path):
        """Extract the tarball into the configured toolchain directory."""
        extract_parent = os.path.dirname(self.toolchain_dir)

        print_log("INFO", f"Extracting {tarball_path}...", tab_level=3)

        with tarfile.open(tarball_path, "r:xz") as tar:
            tar.extractall(path=extract_parent)
            top_dirs = [
                member.name.split("/")[0]
                for member in tar.getmembers()
                if member.isdir()
            ]
            top_level_dir = os.path.commonprefix(top_dirs)

        extracted_folder = os.path.join(extract_parent, top_level_dir)

        if os.path.exists(self.toolchain_dir):
            if os.path.isfile(self.toolchain_dir):
                os.remove(self.toolchain_dir)
            else:
                shutil.rmtree(self.toolchain_dir)

        os.rename(extracted_folder, self.toolchain_dir)
        print_log("INFO", f"Extracted to {self.toolchain_dir}", tab_level=3)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self):
        """Download, extract, and verify the toolchain."""
        compiler_path = shutil.which(self._GCC_NAME)
        is_installed = False

        if compiler_path:
            result = subprocess.run(
                [compiler_path, "--version"],
                stdout=subprocess.PIPE,
                text=True,
                check=False,
            )
            version_line = result.stdout.splitlines()[0] if result.stdout else ""
            if self._VERSION_CHECK is None or self._VERSION_CHECK in version_line:
                is_installed = True

        if not is_installed:
            toolchain_dir, need_extract = self._fetch_sources()
            if need_extract:
                self._extract(toolchain_dir)
            return f"{toolchain_dir}/bin/{self._PREFIX_SUFFIX}"

        print_log("INFO", f"{self._GCC_NAME} already installed and up to date.", tab_level=3)
        return self._PREFIX_SUFFIX

    # ------------------------------------------------------------------
    # Public aliases (match the API of tarball-based toolchain classes)
    # ------------------------------------------------------------------

    def fetch_sources(self):
        """Download the toolchain tarball if it is not already present."""
        return self._fetch_sources()

    def extract(self, tarball_path):
        """Extract the downloaded toolchain tarball into the toolchain directory."""
        self._extract(tarball_path)


# ── Tarball-based toolchain base class (gz archives, e.g. RISC-V, V850) ─────

class TarballToolchainBase:
    """Base class for toolchains distributed as .tar.gz archives on GitHub.

    Subclasses must define:
        _GCC_NAME       – e.g. "riscv64-unknown-elf-gcc"
        _PREFIX_SUFFIX  – e.g. "riscv64-unknown-elf-"
        _VERSION_SUBSTR – optional version check string passed to check_system_gcc

    Subclasses may override:
        _tarball_filename() – return the .tar.gz filename
        _tarball_path()     – return full path to local tarball
        _download_url()     – return the download URL
    """

    _GCC_NAME: str = ""
    _PREFIX_SUFFIX: str = ""
    _VERSION_SUBSTR: str | None = None

    def __init__(self, toolchain_dir, host_platform="x86_64"):
        """Initialize toolchain paths and download metadata."""
        self.toolchain_dir = toolchain_dir
        self.toolchain_parent = os.path.dirname(self.toolchain_dir)
        self.host_platform = host_platform

        self.toolchain_prefix = os.path.join(self.toolchain_dir, "bin", self._PREFIX_SUFFIX)
        self.toolchain_gcc = f"{self.toolchain_prefix}gcc"

        os.makedirs(self.toolchain_parent, exist_ok=True)

    # ------------------------------------------------------------------
    # Overrideable descriptors
    # ------------------------------------------------------------------

    def _tarball_filename(self):
        """Return the archive filename (override in subclass)."""
        raise NotImplementedError

    def _tarball_path(self):
        """Return the full local path for the downloaded tarball."""
        return os.path.join(self.toolchain_parent, self._tarball_filename())

    def _download_url(self):
        """Return the download URL (override in subclass)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prefix_candidates(self):
        return [
            os.path.join(self.toolchain_dir, "bin", self._PREFIX_SUFFIX),
            os.path.join(self.toolchain_parent, "bin", self._PREFIX_SUFFIX),
        ]

    def _resolve_local_prefix(self):
        """Resolve an already installed local compiler prefix if present."""
        prefix = resolve_local_prefix(self._prefix_candidates())
        if prefix:
            self.toolchain_prefix = prefix
            self.toolchain_gcc = f"{prefix}gcc"
        return prefix

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_sources(self):
        """Download the toolchain tarball when a local toolchain is missing."""
        tarball_path = self._tarball_path()

        if self._resolve_local_prefix():
            print_log("INFO", "Toolchain already exists locally", tab_level=3)
            return tarball_path, False

        need_extract = fetch_tarball(self._download_url(), tarball_path, print_log)
        return tarball_path, need_extract

    def extract(self, tarball_path):
        """Extract the downloaded toolchain tarball into the toolchain directory."""
        extract_tarball(tarball_path, self.toolchain_parent, self.toolchain_dir, print_log)

        if not self._resolve_local_prefix():
            raise RuntimeError(
                f"{self._GCC_NAME} toolchain install failed after extraction: "
                f"missing compiler at {self.toolchain_gcc} and "
                f"{os.path.join(self.toolchain_parent, 'bin', self._GCC_NAME)}"
            )

        print_log("INFO", f"Extracted to {self.toolchain_dir}", tab_level=3)

    def install(self):
        """Install the toolchain locally or return the system compiler prefix."""
        if check_system_gcc(self._GCC_NAME, version_substr=self._VERSION_SUBSTR):
            print_log("INFO", f"{self._GCC_NAME} already installed.", tab_level=3)
            return self._PREFIX_SUFFIX

        tarball_path, need_extract = self.fetch_sources()
        if need_extract:
            self.extract(tarball_path)

        if not self._resolve_local_prefix():
            raise RuntimeError(
                f"{self._GCC_NAME} toolchain install failed: "
                f"missing compiler at {self.toolchain_gcc}"
            )

        return self.toolchain_prefix
