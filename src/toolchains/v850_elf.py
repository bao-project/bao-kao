"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
V850 ELF toolchain download, extraction, and discovery helpers.
"""

from __future__ import annotations

from utils.toolchain_helpers import TarballToolchainBase  # pylint: disable=import-error


class V850Elf(TarballToolchainBase):
    """Manage installation and discovery of the V850 ELF toolchain."""

    _GCC_NAME = "v850-elf-gcc"
    _PREFIX_SUFFIX = "v850-elf-"
    _TOOLCHAIN_VERSION = "v14.2.0"
    _VERSION_SUBSTR = "v850"

    def _tarball_filename(self):
        return "gcc-14.2.0-v850-elf.tar.gz"

    def _download_url(self):
        return (
            "https://github.com/bao-project/gcc-v850-elf-toolchain/"
            f"releases/download/{self._TOOLCHAIN_VERSION}/{self._tarball_filename()}"
        )


v850_elf = V850Elf  # pylint: disable=invalid-name
