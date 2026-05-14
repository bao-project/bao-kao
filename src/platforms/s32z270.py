"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Platform support for the NXP S32Z270 target.
"""

import os
import shutil
import subprocess
import sys

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

for _p in (
    os.path.abspath(os.path.join(CUR_DIR, "../firmware")),
    os.path.abspath(os.path.join(CUR_DIR, "../toolchains")),
    os.path.abspath(os.path.join(CUR_DIR, "../")),
):
    if _p not in sys.path:
        sys.path.append(_p)

# pylint: disable=duplicate-code
from arm_none_eabi import arm_none_eabi  # pylint: disable=wrong-import-position
# pylint: disable=duplicate-code
from generic_platform import generic_platform  # pylint: disable=wrong-import-position

TIMER_FREQ = 40_000_000  # Hz
CPU_FREQ = 1_000_000_000  # Hz


class s32z270(generic_platform):  # pylint: disable=invalid-name,too-many-instance-attributes
    """Platform definition for the S32Z270 board."""

    def __init__(self, wrkdir):
        """
        Initialize platform paths, architecture data, and runtime properties.

        Args:
            wrkdir (str): Working directory used by the framework.
        """
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/arm_none_eabi"
        self.toolchain_prefix = "arm-none-eabi-"
        self.architecture = "aarch32"
        self.irq_flags = {}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ

        os.makedirs(self.firmware_dir, exist_ok=True)

    def setup_platform(self):
        """Perform any platform-specific setup steps."""

    def build_toolchain(self):
        """Install the ARM embedded toolchain for the current host."""
        host_architecture = subprocess.check_output(
            ["uname", "-m"]
        ).decode().strip()
        toolchain_instance = arm_none_eabi(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, run_bin=None, interrupt_flags=None):  # pylint: disable=unused-argument
        """
        Build the platform firmware artifacts.

        Args:
            run_bin (str | None): Path to the runtime binary.
            interrupt_flags (object | None): Interrupt-related build options.
        """

    @staticmethod
    def get_serial_ports():
        """
        Return the serial ports used by this platform.

        Returns:
            list[str]: Serial device paths.
        """
        return ["/dev/ttyUSB0"]

    def launch_test(
        self,
        run_bin,
        interrupt_flags,
        guest_bins=None,
        guest_os="baremetal",
        hypervisor=None,
    ):  # pylint: disable=too-many-arguments,unused-argument
        """
        Launch a test session through Lauterbach Trace32.

        Args:
            run_bin (str): Path to the main runtime binary.
            interrupt_flags (object): Interrupt-related runtime options.
            guest_bins (str | None): Directory containing guest binaries.
            guest_os (str): Guest OS type.
            hypervisor (str | None): Hypervisor selection.

        Returns:
            subprocess.Popen: Result from the command launcher.
        """
        launch_script_path = os.path.join(CUR_DIR, "s32z270", "t32.cmm")
        windows_script_path = os.path.join(CUR_DIR, "s32z270", "windows.cmm")

        cmd = ["t32marm", "-s", launch_script_path, windows_script_path]

        if hypervisor is not None and hypervisor != "none":
            run_elf = run_bin.replace(".bin", ".elf")
            run_img = os.path.join(self.firmware_dir, "run.elf")
            shutil.copy(run_elf, run_img)
            cmd.append(run_img)

        if guest_bins:
            for guest_bin in os.listdir(guest_bins):
                if guest_bin.endswith(".elf"):
                    cmd.append(os.path.join(guest_bins, guest_bin))

        return super().run_command(cmd, log_tab_level=2)
