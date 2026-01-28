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

class s32:
    def __init__(self, wrkdir):
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.srcs_dir = f"{wrkdir}/platforms/qemu_aarch64_virt"
        # self.qemu_version = "7.2.0"
        # self.git_repo = "https://git.qemu.org/git/qemu.git"
        self.firmware = {}
        self.toolchain = f"{wrkdir}/toolchains/arm_none_eabi"
        self.architecture = "aarch64"

        
        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        pass
            
    def build_toolchain(self):
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = arm_none_eabi(self.toolchain, host_architecture)
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

    def launch_test(self, bao_img, interrupt_flags, guest_os="baremetal"):
        pass