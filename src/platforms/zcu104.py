"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Platform support for the Xilinx ZCU104 target.
"""

# pylint: disable=duplicate-code
import importlib
import os
import shutil
import sys
import subprocess
import tempfile
import textwrap

CUR_DIR = os.path.dirname(os.path.abspath(__file__))

for _p in (
    os.path.abspath(os.path.join(CUR_DIR, "../toolchains")),
    os.path.abspath(os.path.join(CUR_DIR, "../firmware")),
    os.path.abspath(os.path.join(CUR_DIR, "../")),
):
    if _p not in sys.path:
        sys.path.append(_p)

aarch64_none_elf = getattr(importlib.import_module("aarch64_none_elf"), "aarch64_none_elf")
generic_platform = getattr(importlib.import_module("generic_platform"), "generic_platform")
uboot = getattr(importlib.import_module("uboot"), "uboot")
print_log = getattr(importlib.import_module("constants"), "print_log")



TIMER_FREQ = 100_000_000  # Hz
CPU_FREQ = 1_200_000_000  # Hz


def generate_boot_txt(
    mode: str,
    artifact_route: str,
    use_uboot_image: bool = False,
    bao_addr: str = "0x200000",
    standalone_addr: str = "0x20000000",
) -> str:
    """
    Generate the U-Boot boot script text for HTTP boot.

    Args:
        mode (str): Boot mode, either "bao" or "none".
        artifact_route (str): HTTP route of the payload artifact.
        use_uboot_image (bool): Whether the payload is a U-Boot image.
        bao_addr (str): Load address for Bao mode.
        standalone_addr (str): Load address for standalone mode.

    Returns:
        str: Generated boot.txt contents.
    """
    if mode == "standalone":
        mode = "none"

    if mode not in ("bao", "none"):
        raise ValueError(f"Unsupported mode: {mode}")

    load_addr = bao_addr if mode == "bao" else standalone_addr

    lines = ["setenv autoload no", "dhcp"]
    if use_uboot_image:
        lines += [f"wget {load_addr} {artifact_route}", "bootm"]
    else:
        lines += [f"wget {load_addr} {artifact_route}", "sleep 2", f"go {load_addr}"]

    return "\n".join(lines) + "\n"


def make_boot_scr(
    boot_txt_path: str,
    boot_scr_path: str,
    mkimage: str = "mkimage",
):
    """
    Generate a U-Boot boot.scr from boot.txt.

    Args:
        boot_txt_path (str): Path to the input boot.txt file.
        boot_scr_path (str): Path to the output boot.scr file.
        mkimage (str): mkimage executable name or path.
    """
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
    """
    Stage payload and boot script files for HTTP boot.

    Args:
        run_path (str): Path to the runtime payload.
        mode (str): Boot mode, either "bao" or "none".
        use_uboot_image (bool): Whether the payload is a U-Boot image.
        workdir (str | None): Optional staging directory.
        mkimage (str): mkimage executable name or path.

    Returns:
        dict: Paths and HTTP routes for the staged artifacts.
    """
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
        shutil.copy(run_path, staged_run_path)

    boot_txt = generate_boot_txt(
        mode=mode,
        artifact_route=artifact_route,
        use_uboot_image=use_uboot_image,
    )
    with open(boot_txt_path, "w", encoding="utf-8", newline="\n") as boot_txt_file:
        boot_txt_file.write(boot_txt)

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
):  # pylint: disable=too-many-arguments
    """
    Start a temporary HTTP server for U-Boot auto-boot artifacts.

    Args:
        run_path (str): Path to the runtime payload.
        mode (str): Boot mode.
        bind (str): Bind address for the HTTP server.
        once (bool): Shut down after serving the payload once.
        quiet (bool): Suppress server logging.
        use_uboot_image (bool): Whether the payload is a U-Boot image.
        mkimage (str): mkimage executable name or path.

    Returns:
        subprocess.Popen: Process handle of the spawned HTTP server.
    """
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

    server_code = textwrap.dedent(
        f"""
# pylint: disable=duplicate-code
import os, threading
# pylint: disable=duplicate-code
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
# pylint: disable=duplicate-code
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
            with open(file_path, "rb") as served_file:
                while True:
                    chunk = served_file.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

        if ONCE and (not head_only) and path == {artifact_route!r}:
            threading.Thread(
                target=self.server.shutdown,
                daemon=True,
            ).start()

httpd = ThreadingHTTPServer((BIND, 80), H)
if not QUIET:
    print("Serving boot artifacts:")
    for route, file_path in ROUTES.items():
        print(f"  http://{{BIND}}:80{{route}} -> {{file_path}}")
httpd.serve_forever()
"""
    )

    proc = subprocess.Popen(  # pylint: disable=consider-using-with
        ["sudo", sys.executable, "-c", server_code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc


class zcu104(generic_platform):  # pylint: disable=invalid-name,too-many-instance-attributes
    """Platform definition for the Xilinx ZCU104 board."""

    def __init__(self, wrkdir):
        """
        Initialize platform paths, toolchain data, and firmware settings.

        Args:
            wrkdir (str): Framework working directory.
        """
        super().__init__(wrkdir)
        self.firmware_dir = f"{wrkdir}/platforms/firmware"
        self.firmware = {}
        self.prebuilt_firmware = "https://github.com/Xilinx/soc-prebuilt-firmware.git"
        self.prebuilt_firmware_version = "xlnx_rel_v2023.1"
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.toolchain_prefix = "aarch64-none-elf-"
        self.architecture = "aarch64"
        self.irq_flags = {'GIC_version': "GICV2"}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ
        self.platform_name = "zcu104"

        os.makedirs(self.firmware_dir, exist_ok=True)

    def setup_platform(self): # pylint: disable=no-self-use
        """Perform any platform-specific setup steps."""
        return

    def build_toolchain(self):
        """Install the AArch64 bare-metal toolchain for the current host."""
        host_architecture = subprocess.check_output(
            ["uname", "-m"]
        ).decode().strip()
        toolchain_instance = aarch64_none_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()

    def build_firmware(self, _run_bin=None, _interrupt_flags=None):
        """
        Build firmware artifacts required by the ZCU104 platform.

        Args:
            _run_bin (str | None): Unused runtime binary path.
            _interrupt_flags (object | None): Unused interrupt-related options.
        """
        uboot_instance = uboot(self.firmware_dir)
        uboot_bin = uboot_instance.build("zcu104", self.toolchain)
        uboot_elf = uboot_bin.replace(".bin", ".elf")

        clone_cmd = [
            "git", "clone",
            "--branch", self.prebuilt_firmware_version,
            self.prebuilt_firmware,
            f"{self.firmware_dir}/prebuilt_firmware",
        ]

        prebuilt_dir = f"{self.firmware_dir}/prebuilt_firmware"
        if os.path.exists(prebuilt_dir):
            shutil.rmtree(prebuilt_dir)

        super().run_command(clone_cmd, cwd=self.firmware_dir, log_tab_level=2).wait()

        boot_bin_path = f"{self.firmware_dir}/prebuilt_firmware/zcu104-zynqmp"
        shutil.copy(uboot_elf, os.path.join(boot_bin_path, "u-boot.elf"))

        bootgen_cmd = [
            "bootgen",
            "-arch", "zynqmp",
            "-image", "bootgen.bif",
            "-w",
            "-o", f"{boot_bin_path}/BOOT.bin",
        ]
        super().run_command(bootgen_cmd, cwd=boot_bin_path, log_tab_level=2)

    @staticmethod
    def get_serial_ports():
        """
        Return the serial ports used by this platform.

        Returns:
            list[str]: Serial device paths.
        """
        return ["/dev/ttyUSB1"]

    def launch_test(
        self,
        run_bin,
        _interrupt_flags,
        _guest_bins=None,
        _guest_os="baremetal",
        hypervisor=None,
    ):  # pylint: disable=too-many-arguments
        """
        Launch a ZCU104 test by serving the runtime over HTTP for U-Boot.

        Args:
            run_bin (str): Path to the runtime binary.
            _interrupt_flags (object): Unused interrupt-related options.
            _guest_bins (str | None): Unused guest binaries path.
            _guest_os (str): Unused guest OS name.
            hypervisor (str | None): Hypervisor mode for boot script generation.

        Returns:
            subprocess.Popen: Process handle of the temporary HTTP server.
        """
        shutil.copy(run_bin, os.path.join(self.firmware_dir, "run.bin"))
        run_img = os.path.join(self.firmware_dir, "run.bin")

        print_log(
            "INFO",
            "Please flash the BOOT.bin to the SD card and insert it into the board.",
            tab_level=1,
        )
        return serve_uboot_http_auto(run_img, mode=hypervisor, use_uboot_image=False)
