# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import shutil
import subprocess
import urllib.request
import tarfile
import os
import sys
import socket
import tempfile

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../firmware")))
from atf import atf
from uboot import uboot

sys.path.append(os.path.abspath(os.path.join(cur_dir, "../toolchains")))
from aarch64_none_elf import aarch64_none_elf


sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

from generic_platform import generic_emulator

TIMER_FREQ = 40000000 #Hz
CPU_FREQ = 1000000000 #Hz
GIC_VERSIONS = ["GICV3", "GICV2"]

class qemu_aarch64_virt(generic_emulator):
    def __init__(self, wrkdir):
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

        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        path = shutil.which("qemu-system-aarch64")
        is_installed = False
        if(path is not None):
            is_installed = True
            print_log("INFO", f"QEMU {self.qemu_version} is already installed", tab_level=1)

        if not is_installed:
            print_log("INFO", f"QEMU not found or wrong version. Installing...", tab_level=1)
            if not os.path.exists(self.srcs_dir):
               os.makedirs(self.srcs_dir)

            print_log("INFO", f"Cloning {self.git_repo}...", tab_level=1)

            if not os.path.exists(self.srcs_dir) or not os.listdir(self.srcs_dir):
                super().run_command(["git", "clone", "--branch", f"v{self.qemu_version}",
                            "--recurse-submodules", "--depth", "1",
                            self.git_repo, self.srcs_dir])

            print_log("INFO", f"Configuring QEMU...", tab_level=1)
            super().run_command(["./configure", "--target-list=aarch64-softmmu", "--enable-slirp"],
                        cwd=self.srcs_dir)

            print_log("INFO", f"Building QEMU (this may take a while)...", tab_level=1)
            super().run_command(["make", f"-j{os.cpu_count()}"],
                        cwd=self.srcs_dir)

            print_log("INFO", f"Installing QEMU (sudo may prompt for password)...", tab_level=1)
            super().run_command(["sudo", "make", "install"],
                        cwd=self.srcs_dir)

            print_log("SUCCESS", f"QEMU {self.qemu_version} installed successfully!", tab_level=1)

    def build_toolchain(self):
        print_log("INFO", f"Setting up toolchain...", tab_level=1)
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = aarch64_none_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("SUCCESS", f"Toolchain set up successfully!", tab_level=1)

    def build_firmware(self, run_bin=None, interrupt_flags=None):
        if interrupt_flags:
            gic_version = interrupt_flags.get("GIC_version", "GICV2")

        uboot_instance = uboot(self.firmware_dir)
        uboot_bin = uboot_instance.build("qemu-aarch64-virt", self.toolchain)

        atf_instance = atf(self.firmware_dir)
        atf_instance.build("qemu-aarch64-virt", uboot_bin, self.toolchain, gic_version)
        atf_instance.install("qemu-aarch64-virt", self.firmware_dir)

    def launch_test(self, run_bin, interrupt_flags, guests_bins, guest_os="baremetal", hypervisor=None):
        if interrupt_flags:
            gic_version = interrupt_flags.get("GIC_version", "GICV2")
            gic_version = gic_version.replace("GICV", "")
        else:
            gic_version = "2"

        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

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

        qemu_stderr = tempfile.NamedTemporaryFile(delete=False)
        qemu_stderr_path = qemu_stderr.name
        qemu_stderr.close()

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
        ] + extra_serial_args

        print_log("INFO", f"Launching QEMU...", tab_level=0)
        errf = open(qemu_stderr_path, "wb")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,   # optional, for logging/errors
            text=True,
            bufsize=1
        )

        pty_ports = []

        while True:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    raise RuntimeError(f"QEMU exited with code {proc.returncode}")
                continue

            if "char device redirected to " in line:
                pty = line.split("char device redirected to ", 1)[1].split(" ", 1)[0].strip()
                pty_ports.append(pty)
                break

        return proc, qemu_stderr_path, errf, pty_ports
