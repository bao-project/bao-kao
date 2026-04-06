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
from arm_none_eabi import arm_none_eabi

from generic_platform import generic_platform

TIMER_FREQ = 40000000 #Hz
CPU_FREQ = 1000000000 #Hz

class s32z270(generic_platform):
    def __init__(self, wrkdir):
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/arm_none_eabi"
        self.architecture = "aarch32"
        self.irq_flags = {},
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ

        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        pass
            
    def build_toolchain(self):
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = arm_none_eabi(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, run_bin=None, interrupt_flags=None):
        # self.build_toolchain()
        pass

    def get_serial_ports(self):
        return ["/dev/ttyUSB1"]

    def launch_test(self, run_bin, interrupt_flags, guest_bins = None, guest_os="baremetal", hypervisor=None):
        launch_script_path = os.path.join(cur_dir, "s32z270/t32.cmm")
        cmd = ["t32marm", "-s", launch_script_path]

        if hypervisor is not None and hypervisor != "standalone":
            run_elf = run_bin.replace(".bin", ".elf")
            run_img = os.path.join(self.firmware_dir, "run.elf")
            shutil.copy(run_elf, run_img)
            cmd.append(run_img)

        list_guests = os.listdir(guest_bins)
        for guest_bin in list_guests:
            if guest_bin.endswith(".elf"):
                cmd.append(os.path.join(guest_bins, guest_bin))
        proc = super().run_command(cmd, log_tab_level=2)
        return proc
