"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Platform support for the TC4DX target.
"""

# pylint: disable=duplicate-code
import os
import subprocess
import sys

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

for _p in (
    os.path.abspath(os.path.join(CUR_DIR, "../toolchains")),
    os.path.abspath(os.path.join(CUR_DIR, "../firmware")),
):
    if _p not in sys.path:
        sys.path.append(_p)

# pylint: disable=duplicate-code
from tricore_elf import tricore_elf  # pylint: disable=wrong-import-position


class tc4dx:  # pylint: disable=invalid-name
    """Platform definition for the TC4DX target."""

    def __init__(self, wrkdir):
        """
        Initialize platform paths and toolchain configuration.

        Args:
            wrkdir (str): Working directory used by the framework.
        """
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/tricore_elf"
        self.toolchain_prefix = "tricore-elf-"
        self.architecture = "tc4"

        os.makedirs(self.firmware_dir, exist_ok=True)

    @staticmethod
    def setup_platform():
        """Perform any platform-specific setup steps."""
        return None

    def build_toolchain(self):
        """Install the TriCore toolchain for the current host."""
        host_architecture = subprocess.check_output(
            ["uname", "-m"]
        ).decode().strip()
        toolchain_instance = tricore_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, _run_bin=None, _interrupt_flags=None):
        """
        Build the platform firmware artifacts.

        Args:
            _run_bin (str | None): Unused runtime binary path.
            _interrupt_flags (object | None): Unused interrupt-related build options.
        """
        self.build_toolchain()

    @staticmethod
    def launch_test(
        _bao_img,
        _interrupt_flags,
        _guest_bins=None,
        _guest_os="baremetal",
        _hypervisor=None,
    ):
        """
        Launch a test for the TC4DX platform.

        Args:
            _bao_img (str): Path to the Bao image.
            _interrupt_flags (object): Interrupt-related runtime options.
            _guest_bins (str | None): Unused guest binaries path.
            _guest_os (str): Unused guest OS type.
            _hypervisor (str | None): Unused hypervisor selection.

        Returns:
            tuple: Process handle, stderr path, stderr file handle, serial ports.
        """
        proc = None
        stderr_path = None
        errf = None
        serial_ports = []
        return proc, stderr_path, errf, serial_ports
