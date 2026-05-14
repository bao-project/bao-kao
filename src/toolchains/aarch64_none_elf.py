"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
AArch64 none-elf toolchain download, extraction, and discovery helpers.
"""

from __future__ import annotations

from utils.toolchain_helpers import ArmGnuToolchainBase  # pylint: disable=import-error


class Aarch64NoneElf(ArmGnuToolchainBase):
    """Manage installation and discovery of the AArch64 none-elf toolchain."""

    _GCC_NAME = "aarch64-none-elf-gcc"
    _PREFIX_SUFFIX = "aarch64-none-elf-"
    _TRIPLE_TAG = "aarch64-none-elf"
    _VERSION_CHECK = "14.2.rel1"


aarch64_none_elf = Aarch64NoneElf  # pylint: disable=invalid-name
