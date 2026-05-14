"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
ARM none-eabi toolchain download, extraction, and discovery helpers.
"""

from __future__ import annotations

from utils.toolchain_helpers import ArmGnuToolchainBase  # pylint: disable=import-error


class ArmNoneEabi(ArmGnuToolchainBase):
    """Manage installation and discovery of the ARM none-eabi toolchain."""

    _GCC_NAME = "arm-none-eabi-gcc"
    _PREFIX_SUFFIX = "arm-none-eabi-"
    _TRIPLE_TAG = "arm-none-eabi"
    _VERSION_CHECK = "14.2.rel1"


arm_none_eabi = ArmNoneEabi  # pylint: disable=invalid-name
