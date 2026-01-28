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

class qemu_aarch64_virt:
    def __init__(self, wrkdir):
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.srcs_dir = f"{wrkdir}/platforms/qemu_aarch64_virt"
        self.qemu_version = "7.2.0"
        self.git_repo = "https://git.qemu.org/git/qemu.git"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.architecture = "aarch64"

        
        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        path = shutil.which("qemu-system-aarch64")
        is_installed = False
        if path:
            result = subprocess.run(["qemu-system-aarch64", "--version"], stdout=subprocess.PIPE, text=True)
            version_line = result.stdout.splitlines()[0]
            version_str = version_line.split()[3]
            if version_str == self.qemu_version:
                is_installed = True
        
        if not is_installed:
            print("[INFO] QEMU not found or wrong version. Installing...")
            if not os.path.exists(self.srcs_dir):
               os.makedirs(self.srcs_dir)


            def run_command(command, cwd=None):
                result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                # print all output
                print(result.stdout)
                if result.returncode != 0:
                    print(f"[ERROR] Command '{' '.join(command)}' failed with error:\n{result.stderr}")
                    raise Exception(f"Command '{' '.join(command)}' failed")
                return result.stdout
            
            print(f"[INFO] Cloning {self.git_repo}...")
            # if os.path.exists(self.srcs_dir) and os.listdir(self.srcs_dir):
            #     raise Exception(f"Source directory {self.srcs_dir}\
            #                      already exists and is not empty.")
            #clone only if not already cloned
            if not os.path.exists(self.srcs_dir) or not os.listdir(self.srcs_dir):
                run_command(["git", "clone", "--branch", f"v{self.qemu_version}",
                            "--recurse-submodules", "--depth", "1",
                            self.git_repo, self.srcs_dir])

            print("[INFO] Configuring QEMU...")
            run_command(["./configure", "--target-list=aarch64-softmmu", "--enable-slirp"],
                        cwd=self.srcs_dir)

            print("[INFO] Building QEMU (this may take a while)...")
            run_command(["make", f"-j{os.cpu_count()}"],
                        cwd=self.srcs_dir)

            print("[INFO] Installing QEMU (sudo may prompt for password)...")
            run_command(["sudo", "make", "install"],
                        cwd=self.srcs_dir)
    
            print(f"[INFO] QEMU {self.qemu_version} installed successfully!")
            
    def build_toolchain(self):
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = aarch64_none_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, interrupt_flags=None):
        self.build_toolchain()

        if interrupt_flags:
            gic_version = interrupt_flags.get("GIC_version", "GICV2")

        uboot_instance = uboot(self.firmware_dir)
        uboot_bin = uboot_instance.build("qemu-aarch64-virt", self.toolchain)
    
        atf_instance = atf(self.firmware_dir)
        atf_instance.build("qemu-aarch64-virt", uboot_bin, self.toolchain, gic_version)
        atf_instance.install("qemu-aarch64-virt", self.firmware_dir)

    def check_port_in_use(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
        
    def scan_pts_ports(self):
        """
        Scan available pts ports
        """
        std_out = subprocess.run(['ls', '/dev/pts/'],
                                stdout=subprocess.PIPE,
                                check=True)
        std_out = std_out.stdout.decode('ASCII')
        ports = std_out.split()
        return ports

    def diff_ports(self, ports_init, ports_end):
        """
        Find allocated pts ports
        """
        diff = list(set(ports_end) - set(ports_init))
        return diff


    def launch_test(self, bao_img, interrupt_flags, guest_os="baremetal"):
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
            "-cpu", "cortex-a53",
            "-smp", "4",
            "-m", "4G",
            "-bios", f"{self.firmware_dir}/flash.bin",
            "-device", f"loader,file={bao_img},addr=0x50000000,force-raw=on",
            "-device", "virtio-net-device,netdev=net0",
            "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:5555-:22",
        ] + extra_serial_args

        print("[CMD]", " ".join(cmd))

        initial_pts_ports = self.scan_pts_ports()

        errf = open(qemu_stderr_path, "wb")
        proc = subprocess.Popen(cmd, stderr=errf)

        final_pts_ports = initial_pts_ports
        while final_pts_ports == initial_pts_ports:
            final_pts_ports = self.scan_pts_ports()
            if proc.poll() is not None:
                # QEMU exited early; clean up
                errf.close()
                if os.path.exists(qemu_stderr_path):
                    os.remove(qemu_stderr_path)
                raise RuntimeError(
                    f"Error launching QEMU (exited with code {proc.returncode})"
                )

        diff_ports = self.diff_ports(initial_pts_ports, final_pts_ports)

        return proc, qemu_stderr_path, errf, diff_ports