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

sys.path.append(os.path.abspath(os.path.join(cur_dir, "../toolchains")))
from tricore_elf import tricore_elf

class tc4dx:
    def __init__(self, wrkdir):
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        # self.qemu_version = "7.2.0"
        # self.git_repo = "https://git.qemu.org/git/qemu.git"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/tricore_elf"
        self.architecture = "tc4"

        
        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        print("qualquer")
            
    def build_toolchain(self):
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = tricore_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, interrupt_flags=None):
        self.build_toolchain()

    def launch_test(self, bao_img, interrupt_flags, guest_os="baremetal"):
        print("[INFO] LAUNCH!")

        proc = None
        stderr_path = None
        errf = None
        serial_ports = []

        return proc, stderr_path, errf, serial_ports