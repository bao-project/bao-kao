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

from constants import print_log

from generic_platform import generic_platform


import os
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

import subprocess
import sys
import textwrap

def generate_boot_txt(
    mode: str,
    artifact_route: str,
    use_uboot_image: bool = False,
    bao_addr: str = "0x200000",
    standalone_addr: str = "0x20000000",
) -> str:
    if mode not in ("bao", "standalone"):
        raise ValueError(f"Unsupported mode: {mode}")

    load_addr = bao_addr if mode == "bao" else standalone_addr

    lines = [
        "setenv autoload no",
        "dhcp",
    ]

    if use_uboot_image:
        lines += [
            f"wget {load_addr} {artifact_route}",
            "bootm",
        ]
    else:
        lines += [
            f"wget {load_addr} {artifact_route}",
            f"sleep 2",
            f"go {load_addr}",
        ]

    return "\n".join(lines) + "\n"

def make_boot_scr(boot_txt_path: str, boot_scr_path: str, mkimage: str = "mkimage"):
    subprocess.run(
        [
            mkimage,
            "-T", "script",
            "-A", "arm64",
            "-C", "none",
            "-n", "bao auto boot",
            "-d", boot_txt_path,
            boot_scr_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

def prepare_http_boot_artifacts(
    run_path: str,
    mode: str,
    use_uboot_image: bool = False,
    workdir: str | None = None,
    mkimage: str = "mkimage",
):
    run_path = os.path.abspath(run_path)
    if not os.path.isfile(run_path):
        raise FileNotFoundError(run_path)

    if workdir is None:
        workdir = tempfile.mkdtemp(prefix="bao-http-boot-")

    os.makedirs(workdir, exist_ok=True)

    artifact_name = "run.img" if use_uboot_image else "run.bin"
    artifact_route = f"/{artifact_name}"

    staged_run_path = os.path.join(workdir, artifact_name)
    boot_txt_path = os.path.join(workdir, "boot.txt")
    boot_scr_path = os.path.join(workdir, "boot.scr")

    if os.path.abspath(run_path) != os.path.abspath(staged_run_path):
        subprocess.run(["cp", "-f", run_path, staged_run_path], check=True)

    boot_txt = generate_boot_txt(
        mode=mode,
        artifact_route=artifact_route,
        use_uboot_image=use_uboot_image,
    )

    with open(boot_txt_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(boot_txt)

    make_boot_scr(boot_txt_path, boot_scr_path, mkimage=mkimage)

    return {
        "workdir": workdir,
        "boot_txt": boot_txt_path,
        "boot_scr": boot_scr_path,
        "artifact": staged_run_path,
        "boot_route": "/boot.scr",
        "artifact_route": artifact_route,
    }

def serve_uboot_http_auto(
    run_path: str,
    mode: str,
    bind: str = "0.0.0.0",
    once: bool = True,
    quiet: bool = True,
    use_uboot_image: bool = False,
    mkimage: str = "mkimage",
):
    artifacts = prepare_http_boot_artifacts(
        run_path=run_path,
        mode=mode,
        use_uboot_image=use_uboot_image,
        mkimage=mkimage,
    )

    boot_scr = artifacts["boot_scr"]
    payload = artifacts["artifact"]
    boot_route = artifacts["boot_route"]
    artifact_route = artifacts["artifact_route"]

    server_code = textwrap.dedent(f"""
        import os, threading
        from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse, unquote

        BIND = {bind!r}
        QUIET = {bool(quiet)!r}
        ONCE = {bool(once)!r}

        ROUTES = {{
            {boot_route!r}: {boot_scr!r},
            {artifact_route!r}: {payload!r},
        }}

        class H(BaseHTTPRequestHandler):
            server_version = "bao-http-boot/1.0"

            def log_message(self, fmt, *args):
                if QUIET:
                    return
                super().log_message(fmt, *args)

            def do_HEAD(self):
                self._serve(head_only=True)

            def do_GET(self):
                self._serve(head_only=False)

            def _serve(self, head_only):
                path = unquote(urlparse(self.path).path)
                file_path = ROUTES.get(path)
                if file_path is None:
                    self.send_error(404, "Not Found")
                    return

                st = os.stat(file_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(st.st_size))
                self.end_headers()

                if not head_only:
                    with open(file_path, "rb") as f:
                        while True:
                            b = f.read(1024 * 1024)
                            if not b:
                                break
                            self.wfile.write(b)

                if ONCE and (not head_only) and path == {artifact_route!r}:
                    threading.Thread(target=self.server.shutdown, daemon=True).start()

        httpd = ThreadingHTTPServer((BIND, 80), H)
        if not QUIET:
            print("Serving boot artifacts:")
            for route, file_path in ROUTES.items():
                print(f"  http://{{BIND}}:80{{route}} -> {{file_path}}")
        httpd.serve_forever()
    """)

    # subprocess.run(["sudo", sys.executable, "-c", server_code], check=True)
    proc = subprocess.Popen(["sudo", sys.executable, "-c", server_code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc

class zcu104(generic_platform):
    def __init__(self, wrkdir):
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.prebuilt_firmware = "https://github.com/Xilinx/soc-prebuilt-firmware.git"
        self.prebuilt_firmware_version = "xlnx_rel_v2023.1"
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.toolchain_prefix = "aarch64-none-elf-"
        self.architecture = "aarch64"
        self.irq_flags = {'GIC_version': "GICV3"}

        
        if not os.path.exists(self.firmware_dir):
            os.makedirs(self.firmware_dir)

    def setup_platform(self):
        pass
            
    def build_toolchain(self):
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = aarch64_none_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, run_bin=None, interrupt_flags=None):
        # self.build_toolchain()

        uboot_instance = uboot(self.firmware_dir)

        uboot_bin = uboot_instance.build("zcu104", self.toolchain)
        uboot_elf = uboot_bin.replace(".bin", ".elf")

        cmd = ["git", "clone", "--branch", self.prebuilt_firmware_version, 
               self.prebuilt_firmware, f"{self.firmware_dir}/prebuilt_firmware"]

        if os.path.exists(f"{self.firmware_dir}/prebuilt_firmware"):
            shutil.rmtree(f"{self.firmware_dir}/prebuilt_firmware")

        proc = super().run_command(cmd, cwd=self.firmware_dir, log_tab_level=2)
        proc.wait()

        boot_bin_path =  f"{self.firmware_dir}/prebuilt_firmware/zcu104-zynqmp"
        shutil.copy(uboot_elf, os.path.join(boot_bin_path, "u-boot.elf"))

        cmd = ["bootgen", "-arch", "zynqmp", "-image", "bootgen.bif", "-w", "-o", f"{boot_bin_path}/BOOT.bin"]
        super().run_command(cmd, cwd=boot_bin_path, log_tab_level=2)

    def get_serial_ports(self):
            return ["/dev/ttyUSB1"]

    def launch_test(self, run_bin, interrupt_flags, guest_bins = None, guest_os="baremetal", hypervisor=None):

        # copy the bao_img to the firmware directory to be loaded by u-boot
        shutil.copy(run_bin, os.path.join(self.firmware_dir, "run.bin"))
        run_img = os.path.join(self.firmware_dir, "run.bin")


        print_log("INFO", "Please flash the BOOT.bin to the SD card and insert it into the board.", tab_level=1)

        proc = serve_uboot_http_auto(run_img, mode=hypervisor, use_uboot_image=False)

        return proc