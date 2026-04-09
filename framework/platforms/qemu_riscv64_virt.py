# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import re
import shutil
import subprocess
import sys
import tempfile

cur_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.abspath(os.path.join(cur_dir, "../firmware")))
from opensbi import opensbi

sys.path.append(os.path.abspath(os.path.join(cur_dir, "../toolchains")))
# Adjust this import/class name to your actual helper
from riscv64_unknown_elf import riscv64_unknown_elf

sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

from generic_platform import generic_emulator

TIMER_FREQ = 10000000  # 10 MHz (QEMU RISC-V default)
CPU_FREQ = 1000000000  # 1 GHz


class qemu_riscv64_virt(generic_emulator):
    def __init__(self, wrkdir):
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.srcs_dir = f"{wrkdir}/platforms/qemu_riscv64_virt"
        self.qemu_version = "10.0.2"
        self.git_repo = "https://github.com/qemu/qemu.git"
        self.toolchain = f"{wrkdir}/toolchains"
        self.toolchain_prefix = "riscv64-unknown-elf-"
        self.architecture = "riscv64"
        self.irq_flags = {}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ

        os.makedirs(self.firmware_dir, exist_ok=True)
        os.makedirs(self.srcs_dir, exist_ok=True)

    def setup_platform(self):
        path = shutil.which("qemu-system-riscv64")
        is_installed = path is not None

        if not is_installed:
            print_log("INFO", "QEMU riscv64 not found. Installing...", tab_level=1)

            if not os.path.exists(self.srcs_dir):
                os.makedirs(self.srcs_dir)

            print_log("INFO", f"Cloning {self.git_repo}...", tab_level=1)
            if not os.path.exists(self.srcs_dir) or not os.listdir(self.srcs_dir):
                super().run_command(
                    [
                        "git", "clone",
                        "--branch", f"v{self.qemu_version}",
                        "--recurse-submodules",
                        "--depth", "1",
                        self.git_repo,
                        self.srcs_dir,
                    ],
                    log_tab_level=1,
                ).wait()

            print_log("INFO", "Configuring QEMU...", tab_level=1)
            super().run_command(
                ["./configure", "--target-list=riscv64-softmmu", "--enable-slirp"],
                cwd=self.srcs_dir,
                log_tab_level=1,
            ).wait()

            print_log("INFO", "Building QEMU (this may take a while)...", tab_level=1)
            super().run_command(
                ["make", f"-j{os.cpu_count()}"],
                cwd=self.srcs_dir,
                log_tab_level=1,
            ).wait()

            print_log("INFO", "Installing QEMU (sudo may prompt for password)...", tab_level=1)
            super().run_command(
                ["sudo", "make", "install"],
                cwd=self.srcs_dir,
                log_tab_level=1,
            ).wait()

        print_log("SUCCESS", f"QEMU {self.qemu_version} ready!", tab_level=1)

    def build_toolchain(self):
        print_log("INFO", "Setting up RISC-V toolchain...", tab_level=2)
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = riscv64_unknown_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("SUCCESS", "Toolchain set up successfully!", tab_level=2)

    def build_firmware(self, run_bin=None, interrupt_flags=None):
        if run_bin is None:
            raise RuntimeError("RISC-V firmware build requires run_bin (Bao image path)")

        opensbi_instance = opensbi(self.firmware_dir)
        opensbi_elf = opensbi_instance.build(
            platform="qemu-riscv64-virt",
            payload_bin=run_bin,
            toolchain=self.toolchain,
            fdt_addr="0x80100000",
        )

        final_path = os.path.join(self.firmware_dir, "opensbi.elf")
        shutil.copy(opensbi_elf, final_path)
        print_log("SUCCESS", f"OpenSBI ready at {final_path}", tab_level=2)
        return final_path

    def launch_test(self, run_bin, interrupt_flags, guests_bins, guest_os="baremetal", hypervisor=None):
        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

        opensbi_elf = os.path.join(self.firmware_dir, "opensbi.elf")
        if not os.path.exists(opensbi_elf):
            opensbi_elf = self.build_firmware(run_bin=run_bin, interrupt_flags=interrupt_flags)

        if guest_os == "linux":
            extra_serial_args = [
                "-device", "virtio-serial-device",
                "-chardev", "pty,id=serial3",
                "-device", "virtconsole,chardev=serial3",
                "-serial", "pty",
            ]
        else:
            extra_serial_args = [
                "-serial", "pty",
            ]

        cmd = [
            "qemu-system-riscv64",
            "-nographic",
            "-M", "virt",
            "-cpu", "rv64",
            "-m", "4G",
            "-smp", "4",
            "-bios", opensbi_elf,
            "-device", "virtio-net-device,netdev=net0",
            "-netdev", "user,id=net0,net=192.168.42.0/24,hostfwd=tcp:127.0.0.1:5555-:22"
        ] + extra_serial_args

        print_log("INFO", "Launching QEMU riscv64...", tab_level=0)

        qemu_log = tempfile.NamedTemporaryFile(delete=False)
        qemu_log_path = qemu_log.name
        qemu_log.close()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        pty_ports = []
        pty_re = re.compile(r"char device redirected to (\S+)")

        while True:
            line = proc.stdout.readline()
            if line:
                with open(qemu_log_path, "a", encoding="utf-8") as f:
                    f.write(line)

                match = pty_re.search(line)
                if match:
                    pty_ports.append(match.group(1))
                    break

            else:
                if proc.poll() is not None:
                    raise RuntimeError(f"QEMU exited with code {proc.returncode}")

        return proc, qemu_log_path, None, pty_ports