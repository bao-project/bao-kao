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

TIMER_FREQ = 50000000   # Hz — AURIX TC4x STM
CPU_FREQ   = 100000000   # Hz — AURIX TC4x TriCore

class tc4dx:
    def __init__(self, wrkdir):
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/tricore_elf"
        self.toolchain_prefix = "tricore-elf-"
        self.architecture = "tc4"
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ
        self.is_emulated = False

        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        pass
            
    def build_toolchain(self):
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = tricore_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, run_bin=None, interrupt_flags=None):
        pass

    def get_serial_ports(self):
        return ["/dev/ttyUSB0"]

    def launch_test(self, run_bin, interrupt_flags, guest_bins=None, guest_os="baremetal", hypervisor=None):
        launch_script_path = os.path.join(cur_dir, "tc4dx/t32.cmm")

        cmd = ["t32mtc", "-s", launch_script_path]

        if hypervisor is not None and hypervisor != "standalone":
            run_elf = run_bin.replace(".bin", ".elf")
            run_img = os.path.join(self.firmware_dir, "run.elf")
            shutil.copy(run_elf, run_img)
            cmd.append(run_img)
       
        if guest_bins:
            for guest_bin in os.listdir(guest_bins):
                if guest_bin.endswith(".elf"):
                    cmd.append(os.path.join(guest_bins, guest_bin))

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc