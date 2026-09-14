"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
QEMU RISC-V virt platform support.
"""

# pylint: disable=duplicate-code
from __future__ import annotations

import importlib
import os
import re
import subprocess
import shutil
import tempfile
import sys

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, ".."))
FIRMWARE_DIR = os.path.join(SRC_DIR, "firmware")
TOOLCHAINS_DIR = os.path.join(SRC_DIR, "toolchains")

for _path in (SRC_DIR, FIRMWARE_DIR, TOOLCHAINS_DIR):
    if _path not in sys.path:
        sys.path.append(_path)

OpenSbi = getattr(importlib.import_module("opensbi"), "opensbi")
Riscv64UnknownElf = getattr(
    importlib.import_module("riscv64_unknown_elf"),
    "riscv64_unknown_elf",
)
print_log = getattr(importlib.import_module("constants"), "print_log")
GenericEmulator = getattr(
    importlib.import_module("generic_platform"),
    "generic_emulator",
)

TIMER_FREQ = 10_000_000  # 10 MHz (QEMU RISC-V default)
CPU_FREQ = 1_000_000_000  # 1 GHz


class QemuRiscv64Virt(GenericEmulator):  # pylint: disable=too-many-instance-attributes
    """QEMU RISC-V virt platform backend."""

    def __init__(self, wrkdir):
        """Initialize platform-specific paths and defaults."""
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.srcs_dir = f"{wrkdir}/platforms/qemu_riscv64_virt"
        self.qemu_version = "10.0.2"
        self.git_repo = "https://github.com/qemu/qemu.git"
        self.toolchain = f"{wrkdir}/toolchains/riscv64-unknown-elf"
        self.toolchain_prefix = "riscv64-unknown-elf-"
        self.architecture = "riscv64"
        self.irq_flags = {}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ
        self.platform_name = "qemu-riscv64-virt"
        self.qemu_bin = ""

        os.makedirs(self.firmware_dir, exist_ok=True)
        os.makedirs(self.srcs_dir, exist_ok=True)

    def _supported_qemu(self, qemu_bin):
        """Return whether a QEMU binary matches the supported version."""
        if not qemu_bin or not os.path.isfile(qemu_bin):
            return False
        result = subprocess.run(
            [qemu_bin, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return result.returncode == 0 and f"version {self.qemu_version}" in result.stdout

    def _run_setup_command(self, command, cwd=None):
        """Run a setup command and report its failure immediately."""
        process = super().run_command(command, cwd=cwd, log_tab_level=1)
        _, stderr = process.communicate()
        if process.returncode != 0:
            detail = stderr.strip() if stderr else "no error output"
            raise RuntimeError(
                f"Command failed ({process.returncode}): {' '.join(command)}\n{detail}"
            )

    def setup_platform(self):
        """Locate or build the supported QEMU version."""
        system_qemu = shutil.which("qemu-system-riscv64")
        if self._supported_qemu(system_qemu):
            self.qemu_bin = system_qemu
            return

        local_qemu = os.path.join(self.srcs_dir, "build", "qemu-system-riscv64")
        if self._supported_qemu(local_qemu):
            self.qemu_bin = local_qemu
            return

        print_log(
            "INFO",
            f"Building QEMU riscv64 v{self.qemu_version} locally...",
            tab_level=1,
        )
        os.makedirs(self.srcs_dir, exist_ok=True)

        print_log("INFO", f"Cloning {self.git_repo}...", tab_level=1)
        if not os.listdir(self.srcs_dir):
            self._run_setup_command(
                [
                    "git", "clone",
                    "--branch", f"v{self.qemu_version}",
                    "--recurse-submodules",
                    "--depth", "1",
                    self.git_repo,
                    self.srcs_dir,
                ]
            )

        print_log("INFO", "Configuring QEMU...", tab_level=1)
        self._run_setup_command(
            ["./configure", "--target-list=riscv64-softmmu", "--enable-slirp"],
            cwd=self.srcs_dir,
        )

        print_log("INFO", "Building QEMU (this may take a while)...", tab_level=1)
        self._run_setup_command(
            ["make", f"-j{os.cpu_count()}"],
            cwd=self.srcs_dir,
        )

        if not self._supported_qemu(local_qemu):
            raise RuntimeError(
                f"QEMU build did not produce v{self.qemu_version} at {local_qemu}"
            )

        self.qemu_bin = local_qemu
        print_log("INFO", f"QEMU {self.qemu_version} ready!", tab_level=1)

    def build_toolchain(self):
        """Install or locate the RISC-V toolchain."""
        print_log("INFO", "Setting up RISC-V toolchain...", tab_level=2)
        host_architecture = subprocess.check_output(
            ["uname", "-m"], text=True
        ).strip()
        toolchain_instance = Riscv64UnknownElf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("INFO", "Toolchain set up successfully!", tab_level=2)

    def build_firmware(self, run_bin=None, _interrupt_flags=None):
        """Build the OpenSBI firmware payload for Bao."""
        if run_bin is None:
            raise RuntimeError("RISC-V firmware build requires run_bin (Bao image path)")

        opensbi_instance = OpenSbi(self.firmware_dir)
        opensbi_elf = opensbi_instance.build(
            platform="qemu-riscv64-virt",
            payload_bin=run_bin,
            toolchain=self.toolchain,
            fdt_addr="0x80100000",
        )
        final_path = os.path.join(self.firmware_dir, "opensbi.elf")
        shutil.copy(opensbi_elf, final_path)
        print_log("INFO", f"OpenSBI ready at {final_path}", tab_level=2)
        return final_path

    @staticmethod
    def _serial_args(guest_os):
        """Return guest-specific serial options."""
        if guest_os == "linux":
            return [
                "-device", "virtio-serial-device",
                "-chardev", "pty,id=serial3",
                "-device", "virtconsole,chardev=serial3",
                "-serial", "pty",
            ]
        return ["-serial", "pty"]

    def _qemu_command(self, opensbi_elf, guest_os):
        """Build the QEMU command line."""
        return [
            self.qemu_bin,
            "-nographic",
            "-M", "virt,aia=aplic-imsic,aia-guests=1",
            "-cpu", "rv64,svpbmt=true",
            "-m", "4G",
            "-smp", "4",
            "-bios", opensbi_elf,
            "-device", "virtio-net-device,netdev=net0",
            "-netdev", "user,id=net0,net=192.168.42.0/24,hostfwd=tcp:127.0.0.1:5555-:22",
            *self._serial_args(guest_os),
        ]

    @staticmethod
    def _wait_for_first_pty(process, qemu_log_path):
        """Wait until QEMU reports the first redirected PTY."""
        pty_ports = []
        pty_regex = re.compile(r"char device redirected to (\S+)")
        while True:
            line = process.stdout.readline()
            if line:
                with open(qemu_log_path, "a", encoding="utf-8") as log_file:
                    log_file.write(line)
                match = pty_regex.search(line)
                if match:
                    pty_ports.append(match.group(1))
                    return pty_ports
            elif process.poll() is not None:
                raise RuntimeError(f"QEMU exited with code {process.returncode}")

    def launch_test(  # pylint: disable=too-many-arguments
        self,
        run_bin,
        interrupt_flags,
        _guests_bins,
        guest_os="baremetal",
        _hypervisor=None,
    ):
        """Launch the QEMU instance used for the test."""
        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

        opensbi_elf = os.path.join(self.firmware_dir, "opensbi.elf")
        if not os.path.exists(opensbi_elf):
            opensbi_elf = self.build_firmware(run_bin=run_bin, _interrupt_flags=interrupt_flags)

        cmd = self._qemu_command(opensbi_elf, guest_os)
        print_log("INFO", "Launching QEMU riscv64...", tab_level=0)

        with tempfile.NamedTemporaryFile(delete=False) as qemu_log:
            qemu_log_path = qemu_log.name

        process = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        pty_ports = self._wait_for_first_pty(process, qemu_log_path)
        return process, qemu_log_path, None, pty_ports


qemu_riscv64_virt = QemuRiscv64Virt  # pylint: disable=invalid-name
