"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Platform support for the RH850 target.
"""

# pylint: disable=duplicate-code
import os
import subprocess
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../firmware")))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../toolchains")))

from v850_elf import v850_elf  # pylint: disable=wrong-import-position


class rh850:  # pylint: disable=invalid-name
    """Platform definition for the RH850 target."""

    def __init__(self, wrkdir):
        """
        Initialize platform paths and toolchain configuration.

        Args:
            wrkdir (str): Working directory used by the framework.
        """
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/v850_elf"
        self.toolchain_prefix = "v850-elf-"
        self.architecture = "rh850"

        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    @staticmethod
    def setup_platform():
        """Perform any platform-specific setup steps."""

    def build_toolchain(self):
        """Install the V850 toolchain for the current host."""
        host_architecture = subprocess.check_output(
            ["uname", "-m"]
        ).decode().strip()
        toolchain_instance = v850_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, _run_bin=None, _interrupt_flags=None):
        """
        Build firmware artifacts for the RH850 platform.

        Args:
            _run_bin (str | None): Unused runtime binary path.
            _interrupt_flags (dict | None): Unused interrupt-related settings.
        """
        self.build_toolchain()

    @staticmethod
    def launch_test(bao_img, _interrupt_flags, guest_os="baremetal"):
        """
        Launch a test for the RH850 platform.

        Args:
            bao_img (str): Path to the Bao image.
            _interrupt_flags (dict | None): Unused interrupt-related runtime options.
            guest_os (str): Guest OS type.
        """
