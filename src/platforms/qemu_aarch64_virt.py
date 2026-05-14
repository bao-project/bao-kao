"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
QEMU AArch64 virt platform support.
"""


# pylint: disable=duplicate-code
from __future__ import annotations


import importlib
import os
import shutil
import subprocess
import sys
import tempfile

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(CUR_DIR, "../firmware"))
TOOLCHAINS_DIR = os.path.abspath(os.path.join(CUR_DIR, "../toolchains"))

for _search_path in (SRC_DIR, FIRMWARE_DIR, TOOLCHAINS_DIR):
    if _search_path not in sys.path:
        sys.path.append(_search_path)

Atf = getattr(importlib.import_module("atf"), "atf")
Uboot = getattr(importlib.import_module("uboot"), "uboot")
Aarch64NoneElf = getattr(
    importlib.import_module("aarch64_none_elf"),
    "aarch64_none_elf",
)
print_log = getattr(importlib.import_module("constants"), "print_log")
GenericEmulator = getattr(
    importlib.import_module("generic_platform"),
    "generic_emulator",
)

TIMER_FREQ = 40_000_000  # Hz
CPU_FREQ = 1_000_000_000  # Hz
GIC_VERSIONS = ["GICV3", "GICV2"]


class QemuAarch64Virt(GenericEmulator):  # pylint: disable=too-many-instance-attributes
    """QEMU AArch64 virt platform backend."""

    def __init__(self, wrkdir):
        """Initialize platform-specific paths and defaults."""
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.srcs_dir = f"{wrkdir}/platforms/qemu_aarch64_virt"
        self.qemu_version = "7.2.0"
        self.git_repo = "https://git.qemu.org/git/qemu.git"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.toolchain_prefix = "aarch64-none-elf-"
        self.architecture = "aarch64"
        self.gic = GIC_VERSIONS[0]
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ
        self.platform_name = "qemu-aarch64-virt"

        os.makedirs(self.firmware_dir, exist_ok=True)

    def setup_platform(self):
        """Install QEMU if it is not already available on the host."""
        qemu_path = shutil.which("qemu-system-aarch64")
        if qemu_path is not None:
            print_log(
                "INFO",
                f"QEMU {self.qemu_version} is already installed",
                tab_level=1,
            )
            return

        print_log("INFO", "QEMU not found or wrong version. Installing...", tab_level=1)
        os.makedirs(self.srcs_dir, exist_ok=True)

        print_log("INFO", f"Cloning {self.git_repo}...", tab_level=1)
        if not os.listdir(self.srcs_dir):
            super().run_command(
                [
                    "git", "clone", "--branch", f"v{self.qemu_version}",
                    "--recurse-submodules", "--depth", "1",
                    self.git_repo, self.srcs_dir,
                ],
            ).wait()

        print_log("INFO", "Configuring QEMU...", tab_level=1)
        super().run_command(
            ["./configure", "--target-list=aarch64-softmmu", "--enable-slirp"],
            cwd=self.srcs_dir,
        ).wait()

        print_log("INFO", "Building QEMU (this may take a while)...", tab_level=1)
        super().run_command(
            ["make", f"-j{os.cpu_count()}"],
            cwd=self.srcs_dir,
        ).wait()

        print_log("INFO", "Installing QEMU (sudo may prompt for password)...", tab_level=1)
        super().run_command(
            ["sudo", "make", "install"],
            cwd=self.srcs_dir,
        ).wait()

        print_log("SUCCESS", f"QEMU {self.qemu_version} installed successfully!", tab_level=1)

    def build_toolchain(self):
        """Install or locate the AArch64 bare-metal toolchain."""
        print_log("INFO", "Setting up toolchain...", tab_level=1)
        host_architecture = subprocess.check_output(
            ["uname", "-m"], text=True,
        ).strip()
        toolchain_instance = Aarch64NoneElf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("SUCCESS", "Toolchain set up successfully!", tab_level=1)

    def build_firmware(self, run_bin=None, interrupt_flags=None):  # pylint: disable=unused-argument
        """Build ATF and U-Boot firmware for the QEMU AArch64 platform."""
        gic_version = "GICV3"
        if interrupt_flags:
            gic_version = interrupt_flags.get("GIC_version", "GICV3")

        uboot_instance = Uboot(self.firmware_dir)
        uboot_bin = uboot_instance.build("qemu-aarch64-virt", self.toolchain)

        atf_instance = Atf(self.firmware_dir)
        atf_instance.build("qemu-aarch64-virt", uboot_bin, self.toolchain, gic_version)
        atf_instance.install("qemu-aarch64-virt", self.firmware_dir)

    @staticmethod
    def _serial_args(guest_os):
        """Return guest-specific serial options."""
        if guest_os == "linux":
            return [
                "-device", "virtio-serial-device", "-chardev", "pty,id=serial3",
                "-device", "virtconsole,chardev=serial3", "-serial", "pty",
            ]
        return ["-serial", "pty"]

    @staticmethod
    def _wait_for_first_pty(process, log_path):
        """Wait until QEMU reports the first redirected PTY."""
        pty_ports = []
        while True:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    raise RuntimeError(f"QEMU exited with code {process.returncode}")
                continue

            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write(line)

            if "char device redirected to " in line:
                pty_name = (
                    line.split("char device redirected to ", 1)[1]
                    .split(" ", 1)[0]
                    .strip()
                )
                pty_ports.append(pty_name)
                return pty_ports

    def launch_test(  # pylint: disable=too-many-arguments,too-many-locals,unused-argument
        self,
        run_bin,
        interrupt_flags, guests_bins,
        guest_os="baremetal", hypervisor=None,
    ):
        """Launch QEMU and return the process, log path, and PTY endpoints."""
        if interrupt_flags:
            gic_version = interrupt_flags.get("GIC_version", "GICV3").replace("GICV", "")
        else:
            gic_version = "3"

        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

        with tempfile.NamedTemporaryFile(delete=False) as stderr_tmp:
            stderr_path = stderr_tmp.name

        cmd = [
            "qemu-system-aarch64",
            "-nographic",
            "-M", f"virt,secure=on,virtualization=on,gic-version={gic_version}",
            "-cpu", "cortex-a53,pmu=on",
            "-smp", "4",
            "-m", "4G",
            "-bios", f"{self.firmware_dir}/flash.bin",
            "-device", f"loader,file={run_bin},addr=0x50000000,force-raw=on",
            "-device", "virtio-net-device,netdev=net0",
            "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:5555-:22",
            *self._serial_args(guest_os),
        ]

        print_log("INFO", "Launching QEMU...", tab_level=0)
        process = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        pty_ports = self._wait_for_first_pty(process, stderr_path)
        return process, stderr_path, None, pty_ports


qemu_aarch64_virt = QemuAarch64Virt  # pylint: disable=invalid-name
