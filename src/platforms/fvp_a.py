"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Arm FVP BaseA platform support.
"""

# pylint: disable=duplicate-code
from __future__ import annotations

import glob
import importlib
import os
import sys
import subprocess
import tempfile


CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, ".."))
TOOLCHAINS_DIR = os.path.abspath(os.path.join(CUR_DIR, "../toolchains"))
FIRMWARE_DIR = os.path.abspath(os.path.join(CUR_DIR, "../firmware"))


for _search_path in (SRC_DIR, TOOLCHAINS_DIR, FIRMWARE_DIR):
    if _search_path not in sys.path:
        sys.path.append(_search_path)


print_log = getattr(importlib.import_module("constants"), "print_log")
Aarch64NoneElf = getattr(importlib.import_module("aarch64_none_elf"), "aarch64_none_elf",)
GenericEmulator = getattr(importlib.import_module("generic_platform"), "generic_emulator",)
UBoot = getattr(importlib.import_module("uboot"), "uboot")
Atf = getattr(importlib.import_module("atf"), "atf")


TIMER_FREQ = 100_000_000
CPU_FREQ = 1_000_000_000

# FVP-A fixed load addresses (must match the TF-A/U-Boot boot chain)
_FIP_LOAD_ADDR = 0x08000000
_BAO_LOAD_ADDR = 0x90000000


class FvpA(GenericEmulator):  # pylint: disable=too-many-instance-attributes
    """Arm FVP BaseA (RevC-2xAEMvA) backend."""

    def __init__(self, wrkdir):
        """Initialize platform-specific paths and defaults."""
        super().__init__(wrkdir)

        self.srcs_dir = os.path.join(wrkdir, "platforms", "fvp_a")
        self.model_dir = os.path.join(self.srcs_dir, "FVP_Model_A")
        self.firmware_dir = os.path.join(wrkdir, "platforms", "firmware")
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.architecture = "aarch64"
        self.irq_flags = {"GIC_version": "GICV3", "uart_idx": 0}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ
        self.platform_name = "fvp-a"

        self.fvp_version = "11.28_23"
        self.fvp_tarball = f"FVP_Base_RevC-2xAEMvA_{self.fvp_version}_Linux64.tgz"
        self.fvp_url = (
            "https://developer.arm.com/-/cdn-downloads/permalink/"
            "FVPs-Architecture/FM-11.28/"
            f"FVP_Base_RevC-2xAEMvA_{self.fvp_version}_Linux64.tgz"
        )
        self.fvp_binary_name = "FVP_Base_RevC-2xAEMvA"
        self.default_model_path = os.path.join(
            self.model_dir,
            "Base_RevC_AEMvA_pkg",
            "models",
            "Linux64_GCC-9.3",
            self.fvp_binary_name,
        )

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.srcs_dir, "tmp"), exist_ok=True)
        os.makedirs(self.firmware_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # FVP model
    # ------------------------------------------------------------------

    def find_fvp_binary(self):
        """Return the FVP binary path if the model is already installed."""
        if (
            os.path.isfile(self.default_model_path) and
            os.access(self.default_model_path, os.X_OK)
        ):
            return self.default_model_path

        matches = glob.glob(
            os.path.join(self.model_dir, "**", self.fvp_binary_name), recursive=True,
        )
        for candidate_path in matches:
            if os.path.isfile(candidate_path):
                if os.access(candidate_path, os.X_OK):
                    return candidate_path

        return None

    def setup_platform(self):
        """Download and extract the FVP model when it is not available."""
        fvp_binary = self.find_fvp_binary()
        if fvp_binary:
            print_log("SUCCESS", f"FVP BaseA ready at {fvp_binary}", tab_level=1)
            return fvp_binary

        print_log("INFO", "FVP BaseA model not found. Downloading...", tab_level=1)
        os.makedirs(self.model_dir, exist_ok=True)

        tarball_path = os.path.join(self.model_dir, self.fvp_tarball)
        if not os.path.exists(tarball_path):
            super().run_command(
                ["curl", "-L", self.fvp_url, "-o", tarball_path], cwd=self.model_dir,
                log_tab_level=1,
            ).wait()

        print_log("INFO", "Extracting FVP BaseA model...", tab_level=1)
        super().run_command(
            ["tar", "xzf", tarball_path, "-C", self.model_dir],
            cwd=self.model_dir, log_tab_level=1,
        ).wait()

        fvp_bin = self.find_fvp_binary()
        if not fvp_bin:
            raise RuntimeError(
                "Error extracting FVP model: FVP_Base_RevC-2xAEMvA binary not found"
            )

        print_log("SUCCESS", f"FVP BaseA ready at {fvp_bin}", tab_level=1)
        return fvp_bin

    # ------------------------------------------------------------------
    # Toolchain
    # ------------------------------------------------------------------

    def build_toolchain(self):
        """Install or locate the AArch64 bare-metal toolchain."""
        print_log("INFO", "Setting up toolchain...", tab_level=2)
        host_architecture = subprocess.check_output(["uname", "-m"], text=True,).strip()
        toolchain_instance = Aarch64NoneElf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("SUCCESS", "Toolchain set up successfully!", tab_level=2)

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    def build_firmware(self, run_bin=None, interrupt_flags=None):  # pylint: disable=unused-argument
        """Build U-Boot and TF-A firmware artifacts for FVP-A.

        Delegates to the shared ``uboot`` and ``atf`` helper classes, mirroring
        the pattern used by other platforms such as ``zcu104``.
        """
        print_log("INFO", "Building firmware (U-Boot + TF-A)...", tab_level=1)

        uboot_instance = UBoot(self.firmware_dir)
        uboot_bin = uboot_instance.build("fvp-a", self.toolchain)

        atf_instance = Atf(self.firmware_dir)
        atf_instance.build("fvp-a", uboot_bin, self.toolchain)
        atf_instance.install("fvp-a", self.firmware_dir)

        bl1_bin = os.path.join(self.firmware_dir, "bl1.bin")
        fip_bin = os.path.join(self.firmware_dir, "fip.bin")

        for artifact, label in ((bl1_bin, "bl1.bin"), (fip_bin, "fip.bin")):
            if not os.path.isfile(artifact):
                raise RuntimeError(
                    f"Firmware build failed: {label} not found at {artifact}"
                )

        print_log("SUCCESS", "Firmware build complete.", tab_level=1)
        return {"bl1": bl1_bin, "fip": fip_bin}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup():
        """Perform no extra cleanup for this platform."""
        return None

    # ------------------------------------------------------------------
    # UART helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uart_enable_args():
        """Return UART enable arguments for the model."""
        uart_args = []
        for uart_idx in (0, 1, 2):
            uart_args.extend(
                ["-C", f"bp.pl011_uart{uart_idx}.uart_enable=1"])
        return uart_args

    # ------------------------------------------------------------------
    # Launch
    # ------------------------------------------------------------------

    def launch_test(  # pylint: disable=too-many-arguments,too-many-locals,unused-argument
        self,
        run_bin, interrupt_flags,
        guests_bins=None, guest_os="baremetal",
        hypervisor=None,
    ):
        """Build firmware (if needed), launch the FVP model, and return
        process and log handles.

        ``run_bin`` is the Bao binary (bao.bin).  U-Boot and TF-A are built via
        the shared firmware helpers when not already present.
        """
        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

        fvp_bin = self.setup_platform()

        fw_path = self.build_firmware(run_bin=run_bin, interrupt_flags=interrupt_flags)
        bl1_bin = fw_path["bl1"]
        fip_bin = fw_path["fip"]

        test_uart_idx = 0
        if interrupt_flags and "uart_idx" in interrupt_flags:
            test_uart_idx = int(interrupt_flags["uart_idx"])

        serial_port = f"tcp://127.0.0.1:{5000 + test_uart_idx}"

        cmd = [
            fvp_bin,
            "-C", "cluster0.NUM_CORES=4",
            "-C", "cache_state_modelled=0",
            "-C", "bp.refcounter.use_real_time=1",
            "-C", "bp.exclusive_monitor.monitor_access_level=1",
            "-C", "cluster0.supports_multi_threading=0",
            "-C", "cluster0.mpidr_layout=0",
            "-C", "cluster1.NUM_CORES=0",
            "-C", "pctl.startup=0.0.0.0",
            "-C", "pctl.Affinity-shifted=0",
            "-C", "pctl.CPU-affinities=0.0.0.0, 0.0.0.1, 0.0.0.2, 0.0.0.3",
            "-C", "gic_distributor.CPU-affinities=0.0.0.0, 0.0.0.1, 0.0.0.2, 0.0.0.3",
            "-C", (
                "gic_distributor.reg-base-per-redistributor="
                "0.0.0.0=0x2f100000,0.0.0.1=0x2f120000,"
                "0.0.0.2=0x2f140000,0.0.0.3=0x2f160000"
            ),
            "-C", "bp.smsc_91c111.enabled=true",
            "-C", "bp.hostbridge.userNetworking=true",
            "-C", "bp.hostbridge.userNetSubnet=192.168.42.0/24",
            "-C", "bp.hostbridge.userNetPorts=127.0.0.1:5555=22",
            *self._uart_enable_args(),
            "--data", f"{bl1_bin}@0x0",
            "--data", f"{fip_bin}@{_FIP_LOAD_ADDR:#010x}",
            "--data", f"{run_bin}@{_BAO_LOAD_ADDR:#010x}",
        ]

        print_log("INFO", f"Launching FVP BaseA from: {fvp_bin}", tab_level=0)
        print_log("INFO", f"Framework UART endpoint: {serial_port}", tab_level=1)
        print_log(
            "INFO",
            f"U-Boot bootcmd will auto-run: go {_BAO_LOAD_ADDR:#010x}",
            tab_level=1,
        )

        with tempfile.NamedTemporaryFile(delete=False) as log_tmp:
            fvp_log_path = log_tmp.name

        log_file = open(  # pylint: disable=consider-using-with
            fvp_log_path, "w",
            encoding="utf-8"
        )
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd,
            stdout=log_file, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        return process, fvp_log_path, log_file, [serial_port]


fvp_a = FvpA  # pylint: disable=invalid-name
