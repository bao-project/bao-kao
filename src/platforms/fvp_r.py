"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Arm FVP BaseR platform support.
"""

# pylint: disable=duplicate-code
from __future__ import annotations

import glob
import importlib
import os
import re
import subprocess
import tempfile
import sys

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, ".."))
TOOLCHAINS_DIR = os.path.abspath(os.path.join(CUR_DIR, "../toolchains"))

for _search_path in (SRC_DIR, TOOLCHAINS_DIR):
    if _search_path not in sys.path:
        sys.path.append(_search_path)

print_log = getattr(importlib.import_module("constants"), "print_log")
Aarch64NoneElf = getattr(
    importlib.import_module("aarch64_none_elf"), "aarch64_none_elf",
)
GenericEmulator = getattr(
    importlib.import_module("generic_platform"), "generic_emulator",
)

TIMER_FREQ = 40_000_000
CPU_FREQ = 1_000_000_000


class FvpR(GenericEmulator):  # pylint: disable=too-many-instance-attributes
    """Arm FVP BaseR backend."""

    def __init__(self, wrkdir):
        """Initialize platform-specific paths and defaults."""
        super().__init__(wrkdir)

        self.srcs_dir = os.path.join(wrkdir, "platforms", "fvp_r")
        self.model_dir = os.path.join(self.srcs_dir, "FVP_Model_R")
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.architecture = "aarch64"
        self.irq_flags = {"GIC_version": "GICV3"}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ
        self.platform_name = "fvp-r"

        self.fvp_version = "11.28_23"
        self.fvp_tarball = f"FVP_Base_AEMv8R_{self.fvp_version}_Linux64.tgz"
        self.fvp_url = (
            "https://developer.arm.com/-/cdn-downloads/permalink/"
            "FVPs-Architecture/FM-11.28/"
            "FVP_Base_AEMv8R_11.28_23_Linux64.tgz"
        )
        self.fvp_binary_name = "FVP_BaseR_AEMv8R"
        self.default_model_path = os.path.join(
            self.model_dir,
            "AEMv8R_base_pkg",
            "models",
            "Linux64_GCC-9.3",
            self.fvp_binary_name,
        )
        self.tests_config_dir = os.path.abspath(
            os.path.join(CUR_DIR, "../../../tests/configs")
        )

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.srcs_dir, "tmp"), exist_ok=True)

    def find_fvp_binary(self):
        """Return the FVP binary path if the model is already installed."""
        if (
            os.path.isfile(self.default_model_path)
            and os.access(self.default_model_path, os.X_OK)
        ):
            return self.default_model_path

        matches = glob.glob(
            os.path.join(self.model_dir, "**", self.fvp_binary_name),
            recursive=True,
        )
        for candidate_path in matches:
            if os.path.isfile(candidate_path) and os.access(candidate_path, os.X_OK):
                return candidate_path

        return None

    def setup_platform(self):
        """Download and extract the FVP model when it is not available."""
        fvp_bin = self.find_fvp_binary()
        if fvp_bin:
            print_log("SUCCESS", f"FVP BaseR ready at {fvp_bin}", tab_level=1)
            return fvp_bin

        print_log("INFO", "FVP BaseR model not found. Downloading...", tab_level=1)
        os.makedirs(self.model_dir, exist_ok=True)

        tarball_path = os.path.join(self.model_dir, self.fvp_tarball)
        if not os.path.exists(tarball_path):
            super().run_command(
                ["curl", "-L", self.fvp_url, "-o", tarball_path],
                cwd=self.model_dir,
                log_tab_level=1,
            ).wait()

        print_log("INFO", "Extracting FVP BaseR model...", tab_level=1)
        super().run_command(
            ["tar", "xzf", tarball_path, "-C", self.model_dir],
            cwd=self.model_dir,
            log_tab_level=1,
        ).wait()

        fvp_bin = self.find_fvp_binary()
        if not fvp_bin:
            raise RuntimeError(
                "Error extracting FVP model: FVP_BaseR_AEMv8R binary not found"
            )

        print_log("SUCCESS", f"FVP BaseR ready at {fvp_bin}", tab_level=1)
        return fvp_bin

    def build_toolchain(self):
        """Install or locate the AArch64 bare-metal toolchain."""
        print_log("INFO", "Setting up toolchain...", tab_level=2)
        host_architecture = subprocess.check_output(
            ["uname", "-m"],
            text=True,
        ).strip()
        toolchain_instance = Aarch64NoneElf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("SUCCESS", "Toolchain set up successfully!", tab_level=2)

    @staticmethod
    def build_firmware(run_bin=None, interrupt_flags=None):  # pylint: disable=unused-argument
        """Return no firmware artifact because FVP boots the provided image."""
        return None

    @staticmethod
    def cleanup():
        """Perform no extra cleanup for this platform."""
        return None

    @staticmethod
    def _extract_vm_region_bases(config_file_path):
        """Extract VM region base addresses from a generated Bao config file."""
        with open(config_file_path, encoding="utf-8") as file_handle:
            content = file_handle.read()

        vm_region_blocks = re.findall(
            r"\.regions\s*=\s*\(struct vm_mem_region\[\]\)\s*\{([^}]+)\}",
            content,
            flags=re.DOTALL,
        )
        bases = []
        for block in vm_region_blocks:
            bases.extend(
                base_match.split("=")[1].strip()
                for base_match in re.findall(r"\.base\s*=\s*0x[0-9A-Fa-f]+", block)
            )
        return bases

    def _resolve_config_file(self, interrupt_flags=None):
        """Resolve the Bao config file used to infer guest load addresses."""
        if interrupt_flags:
            for key in ("config_file", "config_path", "bao_config_path"):
                cfg = interrupt_flags.get(key)
                if cfg and os.path.isfile(cfg):
                    return os.path.abspath(cfg)

        if not os.path.isdir(self.tests_config_dir):
            raise FileNotFoundError(
                f"Tests configuration directory not found: {self.tests_config_dir}"
            )

        all_candidates = glob.glob(
            os.path.join(self.tests_config_dir, "**", "*.c"),
            recursive=True,
        )
        if not all_candidates:
            raise FileNotFoundError(
                f"No config files found under: {self.tests_config_dir}"
            )

        preferred = [
            p for p in all_candidates
            if any(tag in os.path.basename(p).lower() for tag in ("fvp-r", "fvp_r", "fvpr"))
        ]
        candidates = preferred if preferred else all_candidates
        candidates.sort(key=os.path.getmtime, reverse=True)

        config_file = candidates[0]
        print_log("INFO", f"Using Bao config: {config_file}", tab_level=1)
        return config_file

    def _normalize_guest_specs(self, guests_bins, interrupt_flags=None):
        """Normalize guest binaries into FVP --data guest@addr arguments."""
        if isinstance(guests_bins, str):
            if os.path.isdir(guests_bins):
                guest_items = sorted(glob.glob(os.path.join(guests_bins, "*.bin")))
            elif guests_bins:
                guest_items = [guests_bins]
            else:
                guest_items = []
        elif isinstance(guests_bins, (list, tuple)):
            guest_items = [item for item in guests_bins if item]
        else:
            guest_items = []

        if not guest_items:
            return []

        if all(isinstance(item, str) and "@" in item for item in guest_items):
            return guest_items

        config_file = self._resolve_config_file(interrupt_flags)
        region_bases = self._extract_vm_region_bases(config_file)

        if len(region_bases) < len(guest_items):
            raise RuntimeError(
                f"Not enough VM region bases in {config_file}: "
                f"found {len(region_bases)}, need {len(guest_items)}"
            )

        guest_specs = [
            f"{guest_path}@0x{int(region_bases[idx], 16):X}"
            for idx, guest_path in enumerate(guest_items)
        ]
        print_log("INFO", f"Guest specs: {guest_specs}", tab_level=1)
        return guest_specs

    @staticmethod
    def _arch_settings(architecture):
        """Return architecture-specific FVP parameter values."""
        if architecture == "aarch64":
            return {
                "has_aarch64": "1",
                "vmsa_supported": "1",
                "sre_enable_action_on_mmap": "2",
                "extend_interrupt_range_support": "1",
            }
        return {
            "has_aarch64": "0",
            "vmsa_supported": "0",
            "sre_enable_action_on_mmap": "0",
            "extend_interrupt_range_support": "0",
        }

    @staticmethod
    def _uart_enable_args():
        """Return UART enable arguments for the model."""
        uart_args = []
        for uart_idx in (0, 1, 2):
            uart_args.extend(["-C", f"bp.pl011_uart{uart_idx}.uart_enable=1"])
        return uart_args

    def launch_test(  # pylint: disable=too-many-arguments,too-many-locals,unused-argument
        self,
        run_bin,
        interrupt_flags,
        guests_bins,
        guest_os="baremetal",
        hypervisor=None,
    ):
        """Launch the FVP model and return process and log handles."""
        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

        fvp_bin = self.setup_platform()

        test_uart_idx = 1
        if interrupt_flags and "uart_idx" in interrupt_flags:
            test_uart_idx = int(interrupt_flags["uart_idx"])

        serial_port = f"tcp://127.0.0.1:{5000 + test_uart_idx}"
        arch_flags = self._arch_settings(getattr(self, "architecture", "aarch64"))
        guest_specs = self._normalize_guest_specs(guests_bins, interrupt_flags)

        vm_data_args = []
        for spec in guest_specs:
            vm_data_args.extend(["--data", spec])

        cmd = [
            fvp_bin,
            "-C", "gic_distributor.has-two-security-states=0",
            "-C", "cluster0.gicv3.cpuintf-mmap-access-level=2",
            "-C", "cluster0.gicv3.SRE-EL2-enable-RAO=1",
            "-C", f"cluster0.has_aarch64={arch_flags['has_aarch64']}",
            "-C", f"cluster0.VMSA_supported={arch_flags['vmsa_supported']}",
            "-C", (
                "cluster0.gicv3.SRE-enable-action-on-mmap="
                f"{arch_flags['sre_enable_action_on_mmap']}"
            ),
            "-C", (
                "cluster0.gicv3.extended-interrupt-range-support="
                f"{arch_flags['extend_interrupt_range_support']}"
            ),
            "-C", "bp.smsc_91c111.enabled=true",
            "-C", "bp.hostbridge.userNetworking=true",
            "-C", "bp.hostbridge.userNetSubnet=192.168.42.0/24",
            "-C", "bp.hostbridge.userNetPorts=127.0.0.1:5555=22",
            "--data", f"{run_bin}@0x0",
            *self._uart_enable_args(),
            *vm_data_args,
        ]

        print_log("INFO", f"Launching FVP BaseR from: {fvp_bin}", tab_level=0)
        print_log("INFO", f"Framework UART endpoint: {serial_port}", tab_level=1)

        with tempfile.NamedTemporaryFile(delete=False) as log_tmp:
            fvp_log_path = log_tmp.name

        log_file = open(  # pylint: disable=consider-using-with
            fvp_log_path, "w", encoding="utf-8"
        )
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        return process, fvp_log_path, log_file, [serial_port]


fvp_r = FvpR  # pylint: disable=invalid-name
