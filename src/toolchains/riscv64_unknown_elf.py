"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
RISC-V ELF toolchain download, extraction, and discovery helpers.
"""

from __future__ import annotations

from utils.toolchain_helpers import TarballToolchainBase  # pylint: disable=import-error


class Riscv64UnknownElf(TarballToolchainBase):
    """Manage installation and discovery of the RISC-V unknown-elf toolchain."""

    _GCC_NAME = "riscv64-unknown-elf-gcc"
    _PREFIX_SUFFIX = "riscv64-unknown-elf-"
    _TOOLCHAIN_VERSION = "gc891d8dc23e"

    def _tarball_filename(self):
        return "riscv64-unknown-elf.tar.gz"

    def _tarball_path(self):
        # Stored as <toolchain_dir>.tar.gz (alongside the dir, not inside parent)
        return f"{self.toolchain_dir}.tar.gz"

    def _download_url(self):
        return (
            "https://github.com/bao-project/bao-riscv-toolchain/releases/download/"
            f"{self._TOOLCHAIN_VERSION}/{self._tarball_filename()}"
        )


riscv64_unknown_elf = Riscv64UnknownElf  # pylint: disable=invalid-name
