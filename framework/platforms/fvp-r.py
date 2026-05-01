# # SPDX-License-Identifier: Apache-2.0
# # Copyright (c) Bao Project and Contributors. All rights reserved.

# import os
# import re
# import subprocess
# import sys
# import tempfile
# import glob
# import signal
# import time

# cur_dir = os.path.dirname(os.path.abspath(__file__))
# sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
# from constants import print_log

# sys.path.append(os.path.abspath(os.path.join(cur_dir, "../toolchains")))
# from aarch64_none_elf import aarch64_none_elf

# from generic_platform import generic_emulator


# TIMER_FREQ = 40000000   # Hz
# CPU_FREQ = 1000000000   # Hz


# class fvp_r(generic_emulator):
#     def __init__(self, wrkdir):
#         super().__init__(wrkdir)

#         self.srcs_dir = os.path.join(wrkdir, "platforms", "fvp_r")
#         self.model_dir = os.path.join(self.srcs_dir, "FVP_Model_R")
#         self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
#         self.toolchain_prefix = "aarch64-none-elf-"
#         self.architecture = "aarch64"
#         self.irq_flags = {"GIC_version": "GICV3"}
#         self.cpu_freq = CPU_FREQ
#         self.timer_freq = TIMER_FREQ

#         self.fvp_version = "11.28_23"
#         self.fvp_tarball = f"FVP_Base_AEMv8R_{self.fvp_version}_Linux64.tgz"
#         self.fvp_url = (
#             "https://developer.arm.com/-/cdn-downloads/permalink/FVPs-Architecture/FM-11.28/FVP_Base_AEMv8R_11.28_23_Linux64.tgz"
#         )

#         self.fvp_binary_name = "FVP_BaseR_AEMv8R"
#         self.default_model_path = os.path.join(
#             self.model_dir,
#             "AEMv8R_base_pkg",
#             "models",
#             "Linux64_GCC-9.3",
#             self.fvp_binary_name,
#         )

#         self.tests_config_dir = os.path.abspath(
#             os.path.join(cur_dir, "../../../tests/configs")
#         )

#         self.socat_procs = []

#         os.makedirs(self.srcs_dir, exist_ok=True)
#         os.makedirs(os.path.join(self.srcs_dir, "tmp"), exist_ok=True)

#     def find_fvp_binary(self):
#         if os.path.isfile(self.default_model_path) and os.access(self.default_model_path, os.X_OK):
#             return self.default_model_path

#         matches = glob.glob(
#             os.path.join(self.model_dir, "**", self.fvp_binary_name),
#             recursive=True,
#         )
#         for path in matches:
#             if os.path.isfile(path) and os.access(path, os.X_OK):
#                 return path

#         return None

#     def setup_platform(self):
#         fvp_bin = self.find_fvp_binary()
#         if fvp_bin:
#             print_log("SUCCESS", f"FVP BaseR ready at {fvp_bin}", tab_level=1)
#             return fvp_bin

#         print_log("INFO", "FVP BaseR model not found. Downloading...", tab_level=1)
#         os.makedirs(self.model_dir, exist_ok=True)

#         tarball_path = os.path.join(self.model_dir, self.fvp_tarball)
#         if not os.path.exists(tarball_path):
#             super().run_command(
#                 ["curl", "-L", self.fvp_url, "-o", tarball_path],
#                 cwd=self.model_dir,
#                 log_tab_level=1,
#             ).wait()

#         print_log("INFO", "Extracting FVP BaseR model...", tab_level=1)
#         super().run_command(
#             ["tar", "xzf", tarball_path, "-C", self.model_dir],
#             cwd=self.model_dir,
#             log_tab_level=1,
#         ).wait()

#         fvp_bin = self.find_fvp_binary()
#         if not fvp_bin:
#             raise RuntimeError("Error extracting FVP model: FVP_BaseR_AEMv8R binary not found")

#         print_log("SUCCESS", f"FVP BaseR ready at {fvp_bin}", tab_level=1)
#         return fvp_bin

#     def build_toolchain(self):
#         print_log("INFO", "Setting up toolchain...", tab_level=2)
#         host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
#         toolchain_instance = aarch64_none_elf(self.toolchain, host_architecture)
#         self.toolchain = toolchain_instance.install()
#         print_log("SUCCESS", "Toolchain set up successfully!", tab_level=2)

#     def build_firmware(self, run_bin=None, interrupt_flags=None):
#         return None

#     def _start_uart_pty_pair(self, uart_idx):
#         tmp_dir = os.path.join(self.srcs_dir, "tmp")
#         os.makedirs(tmp_dir, exist_ok=True)

#         fvp_uart_link = os.path.join(tmp_dir, f"fvp-uart{uart_idx}-fvp")
#         host_uart_link = os.path.join(tmp_dir, f"fvp-uart{uart_idx}-host")

#         for link in [fvp_uart_link, host_uart_link]:
#             if os.path.lexists(link):
#                 os.remove(link)

#         print_log("INFO", f"Creating UART{uart_idx} PTY pair ...", tab_level=1)

#         socat_proc = subprocess.Popen(
#             [
#                 "socat",
#                 "-d",
#                 "-d",
#                 f"PTY,raw,echo=0,link={fvp_uart_link}",
#                 f"PTY,raw,echo=0,link={host_uart_link}",
#             ],
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL,
#             text=True,
#             preexec_fn=os.setsid,
#         )
#         self.socat_procs.append(socat_proc)

#         time.sleep(1)

#         if not os.path.exists(fvp_uart_link) or not os.path.exists(host_uart_link):
#             self.cleanup()
#             raise RuntimeError(f"Failed to create UART{uart_idx} PTY pair with socat")

#         fvp_uart_pts = os.path.realpath(fvp_uart_link)
#         host_uart_pts = os.path.realpath(host_uart_link)

#         print_log("INFO", f"UART{uart_idx} logger PTY available at {host_uart_pts}", tab_level=1)
#         return fvp_uart_pts, host_uart_pts

#     def cleanup(self):
#         for socat_proc in self.socat_procs:
#             try:
#                 if socat_proc.poll() is None:
#                     os.killpg(os.getpgid(socat_proc.pid), signal.SIGTERM)
#             except Exception:
#                 pass
#         self.socat_procs = []

#     def _extract_vm_region_bases(self, config_file_path):
#         with open(config_file_path, encoding="utf-8") as file_handle:
#             content = file_handle.read()

#         vm_region_blocks = re.findall(
#             r'\.regions\s*=\s*\(struct vm_mem_region\[\]\)\s*\{([^}]+)\}',
#             content,
#             flags=re.DOTALL,
#         )

#         bases = []
#         for block in vm_region_blocks:
#             bases += [
#                 base.split("=")[1].strip()
#                 for base in re.findall(r'\.base\s*=\s*0x[0-9A-Fa-f]+', block)
#             ]

#         return bases

#     def _resolve_config_file(self, interrupt_flags=None):
#         if interrupt_flags:
#             for key in ["config_file", "config_path", "bao_config_path"]:
#                 cfg = interrupt_flags.get(key)
#                 if cfg and os.path.isfile(cfg):
#                     return os.path.abspath(cfg)

#         if not os.path.isdir(self.tests_config_dir):
#             raise FileNotFoundError(
#                 f"Tests configuration directory not found: {self.tests_config_dir}"
#             )

#         all_candidates = glob.glob(
#             os.path.join(self.tests_config_dir, "**", "*.c"),
#             recursive=True,
#         )

#         if not all_candidates:
#             raise FileNotFoundError(
#                 f"No config files found under: {self.tests_config_dir}"
#             )

#         preferred = []
#         for path in all_candidates:
#             name = os.path.basename(path).lower()
#             if "fvp-r" in name or "fvp_r" in name or "fvpr" in name:
#                 preferred.append(path)

#         candidates = preferred if preferred else all_candidates
#         candidates.sort(key=os.path.getmtime, reverse=True)

#         config_file = candidates[0]
#         print_log("INFO", f"Using Bao config: {config_file}", tab_level=1)
#         return config_file

#     def _normalize_guest_specs(self, guests_bins, interrupt_flags=None):
#         if isinstance(guests_bins, str):
#             if os.path.isdir(guests_bins):
#                 guest_items = sorted(glob.glob(os.path.join(guests_bins, "*.bin")))
#             elif guests_bins:
#                 guest_items = [guests_bins]
#             else:
#                 guest_items = []
#         elif isinstance(guests_bins, (list, tuple)):
#             guest_items = [item for item in guests_bins if item]
#         else:
#             guest_items = []

#         if not guest_items:
#             return []

#         already_addressed = all(isinstance(item, str) and "@" in item for item in guest_items)
#         if already_addressed:
#             return guest_items

#         config_file = self._resolve_config_file(interrupt_flags)
#         region_bases = self._extract_vm_region_bases(config_file)

#         if len(region_bases) < len(guest_items):
#             raise RuntimeError(
#                 f"Not enough VM region bases in {config_file}: "
#                 f"found {len(region_bases)}, need {len(guest_items)}"
#             )

#         guest_specs = []
#         for idx, guest_path in enumerate(guest_items):
#             addr = f"0x{int(region_bases[idx], 16):X}"
#             guest_specs.append(f"{guest_path}@{addr}")

#         print_log("INFO", f"Guest specs: {guest_specs}", tab_level=1)
#         return guest_specs

#     def launch_test(self, run_bin, interrupt_flags, guests_bins, guest_os="baremetal", hypervisor=None):
#         if self.check_port_in_use("127.0.0.1", 5555):
#             raise RuntimeError("Port 5555 is already in use")

#         fvp_bin = self.setup_platform()
#         uart_indices = [0, 1, 2]
#         uart_pairs = [self._start_uart_pty_pair(uart_idx) for uart_idx in uart_indices]
#         serial_ports = [host_uart_pts for _, host_uart_pts in uart_pairs]

#         arch = getattr(self, "architecture", "aarch64")
#         if arch == "aarch64":
#             has_aarch64 = "1"
#             vmsa_supported = "1"
#             sre_enable_action_on_mmap = "2"
#             extend_interrupt_range_support = "1"
#         else:
#             has_aarch64 = "0"
#             vmsa_supported = "0"
#             sre_enable_action_on_mmap = "0"
#             extend_interrupt_range_support = "0"
            

#         guest_specs = self._normalize_guest_specs(guests_bins, interrupt_flags)

#         vm_data_args = []
#         for spec in guest_specs:
#             vm_data_args.extend(["--data", spec])

#         uart_args = []
#         for uart_idx, (fvp_uart_pts, _) in zip(uart_indices, uart_pairs):
#             uart_args.extend([
#                 "-C", f"bp.pl011_uart{uart_idx}.uart_enable=1",
#                 "-C", f"bp.pl011_uart{uart_idx}.out_file={fvp_uart_pts}",
#                 "-C", f"bp.pl011_uart{uart_idx}.unbuffered_output=1",
#             ])

#         cmd = [
#             fvp_bin,
#             "-C", "gic_distributor.has-two-security-states=0",
#             "-C", "cluster0.gicv3.cpuintf-mmap-access-level=2",
#             "-C", "cluster0.gicv3.SRE-EL2-enable-RAO=1",
#             "-C", f"cluster0.has_aarch64={has_aarch64}",
#             "-C", f"cluster0.VMSA_supported={vmsa_supported}",
#             "-C", f"cluster0.gicv3.SRE-enable-action-on-mmap={sre_enable_action_on_mmap}",
#             "-C", f"cluster0.gicv3.extended-interrupt-range-support={extend_interrupt_range_support}",
#             "-C", "bp.smsc_91c111.enabled=true",
#             "-C", "bp.hostbridge.userNetworking=true",
#             "-C", "bp.hostbridge.userNetSubnet=192.168.42.0/24",
#             "-C", "bp.hostbridge.userNetPorts=127.0.0.1:5555=22",
#             "--data", f"{run_bin}@0x0",
#         ] + uart_args + vm_data_args

#         print_log("INFO", f"Launching FVP BaseR from: {fvp_bin}", tab_level=0)

#         fvp_log = tempfile.NamedTemporaryFile(delete=False)
#         fvp_log_path = fvp_log.name
#         fvp_log.close()

#         logf = open(fvp_log_path, "w", encoding="utf-8")
#         print(cmd)
#         proc = subprocess.Popen(
#             cmd,
#             stdout=logf,
#             stderr=subprocess.STDOUT,
#             text=True,
#             preexec_fn=os.setsid,
#         )

#         return proc, fvp_log_path, logf, serial_ports

import os
import re
import subprocess
import sys
import tempfile
import glob
import signal
import time

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

sys.path.append(os.path.abspath(os.path.join(cur_dir, "../toolchains")))
from aarch64_none_elf import aarch64_none_elf

from generic_platform import generic_emulator

TIMER_FREQ = 40000000
CPU_FREQ = 1000000000


class fvp_r(generic_emulator):
    def __init__(self, wrkdir):
        super().__init__(wrkdir)

        self.srcs_dir = os.path.join(wrkdir, "platforms", "fvp_r")
        self.model_dir = os.path.join(self.srcs_dir, "FVP_Model_R")
        self.toolchain = f"{wrkdir}/toolchains/aarch64-none-elf"
        self.architecture = "aarch64"
        self.irq_flags = {"GIC_version": "GICV3"}
        self.cpu_freq = CPU_FREQ
        self.timer_freq = TIMER_FREQ

        self.fvp_version = "11.28_23"
        self.fvp_tarball = f"FVP_Base_AEMv8R_{self.fvp_version}_Linux64.tgz"
        self.fvp_url = (
            "https://developer.arm.com/-/cdn-downloads/permalink/FVPs-Architecture/FM-11.28/"
            "FVP_Base_AEMv8R_11.28_23_Linux64.tgz"
        )

        self.fvp_binary_name = "FVP_BaseR_AEMv8R"
        self.default_model_path = os.path.join(
            self.model_dir,
            "AEMv8R_base_pkg",
            "models",
            "Linux64_GCC-9.3",
            self.fvp_binary_name,
        )

        self.tests_config_dir = os.path.abspath(
            os.path.join(cur_dir, "../../../tests/configs")
        )

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.srcs_dir, "tmp"), exist_ok=True)

    def find_fvp_binary(self):
        if os.path.isfile(self.default_model_path) and os.access(self.default_model_path, os.X_OK):
            return self.default_model_path

        matches = glob.glob(
            os.path.join(self.model_dir, "**", self.fvp_binary_name),
            recursive=True,
        )
        for path in matches:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        return None

    def setup_platform(self):
        fvp_bin = self.find_fvp_binary()
        if fvp_bin:
            print_log("SUCCESS", f"FVP BaseR ready at {fvp_bin}", tab_level=1)
            return fvp_bin

        print_log("INFO", "FVP BaseR model not found. Downloading...", tab_level=1)
        os.makedirs(self.model_dir, exist_ok=True)

        tarball_path = os.path.join(self.model_dir, self.fvp_tarball)
        if not os.path.exists(tarball_path):
            super().run_command(
                ["curl", "-L", self.fvp_url, "-o", tarball_path],
                cwd=self.model_dir,
                log_tab_level=1,
            ).wait()

        print_log("INFO", "Extracting FVP BaseR model...", tab_level=1)
        super().run_command(
            ["tar", "xzf", tarball_path, "-C", self.model_dir],
            cwd=self.model_dir,
            log_tab_level=1,
        ).wait()

        fvp_bin = self.find_fvp_binary()
        if not fvp_bin:
            raise RuntimeError("Error extracting FVP model: FVP_BaseR_AEMv8R binary not found")

        print_log("SUCCESS", f"FVP BaseR ready at {fvp_bin}", tab_level=1)
        return fvp_bin

    def build_toolchain(self):
        print_log("INFO", "Setting up toolchain...", tab_level=2)
        host_architecture = subprocess.check_output(["uname", "-m"]).decode().strip()
        toolchain_instance = aarch64_none_elf(self.toolchain, host_architecture)
        self.toolchain = toolchain_instance.install()
        print_log("SUCCESS", "Toolchain set up successfully!", tab_level=2)

    def build_firmware(self, run_bin=None, interrupt_flags=None):
        return None

    def cleanup(self):
        pass

    def _extract_vm_region_bases(self, config_file_path):
        with open(config_file_path, encoding="utf-8") as file_handle:
            content = file_handle.read()

        vm_region_blocks = re.findall(
            r'\.regions\s*=\s*\(struct vm_mem_region\[\]\)\s*\{([^}]+)\}',
            content,
            flags=re.DOTALL,
        )

        bases = []
        for block in vm_region_blocks:
            bases += [
                base.split("=")[1].strip()
                for base in re.findall(r'\.base\s*=\s*0x[0-9A-Fa-f]+', block)
            ]

        return bases

    def _resolve_config_file(self, interrupt_flags=None):
        if interrupt_flags:
            for key in ["config_file", "config_path", "bao_config_path"]:
                cfg = interrupt_flags.get(key)
                if cfg and os.path.isfile(cfg):
                    return os.path.abspath(cfg)

        if not os.path.isdir(self.tests_config_dir):
            raise FileNotFoundError(
                f"Tests configuration directory not found: {self.tests_config_dir}"
            )

        all_candidates = glob.glob(
            os.path.join(self.tests_config_dir, "**", "*.c"),
            recursive=True,
        )

        if not all_candidates:
            raise FileNotFoundError(
                f"No config files found under: {self.tests_config_dir}"
            )

        preferred = []
        for path in all_candidates:
            name = os.path.basename(path).lower()
            if "fvp-r" in name or "fvp_r" in name or "fvpr" in name:
                preferred.append(path)

        candidates = preferred if preferred else all_candidates
        candidates.sort(key=os.path.getmtime, reverse=True)

        config_file = candidates[0]
        print_log("INFO", f"Using Bao config: {config_file}", tab_level=1)
        return config_file

    def _normalize_guest_specs(self, guests_bins, interrupt_flags=None):
        if isinstance(guests_bins, str):
            if os.path.isdir(guests_bins):
                guest_items = sorted(glob.glob(os.path.join(guests_bins, "*.bin")))
            elif guests_bins:
                guest_items = [guests_bins]
            else:
                guest_items = []
        elif isinstance(guests_bins, (list, tuple)):
            guest_items = [item for item in guests_bins if item]
        else:
            guest_items = []

        if not guest_items:
            return []

        already_addressed = all(isinstance(item, str) and "@" in item for item in guest_items)
        if already_addressed:
            return guest_items

        config_file = self._resolve_config_file(interrupt_flags)
        region_bases = self._extract_vm_region_bases(config_file)

        if len(region_bases) < len(guest_items):
            raise RuntimeError(
                f"Not enough VM region bases in {config_file}: "
                f"found {len(region_bases)}, need {len(guest_items)}"
            )

        guest_specs = []
        for idx, guest_path in enumerate(guest_items):
            addr = f"0x{int(region_bases[idx], 16):X}"
            guest_specs.append(f"{guest_path}@{addr}")

        print_log("INFO", f"Guest specs: {guest_specs}", tab_level=1)
        return guest_specs

    def launch_test(self, run_bin, interrupt_flags, guests_bins, guest_os="baremetal", hypervisor=None):
        if self.check_port_in_use("127.0.0.1", 5555):
            raise RuntimeError("Port 5555 is already in use")

        fvp_bin = self.setup_platform()

        test_uart_idx = 1
        if interrupt_flags and "uart_idx" in interrupt_flags:
            test_uart_idx = int(interrupt_flags["uart_idx"])

        serial_ports = [f"tcp://127.0.0.1:{5000 + test_uart_idx}"]

        arch = getattr(self, "architecture", "aarch64")
        if arch == "aarch64":
            has_aarch64 = "1"
            vmsa_supported = "1"
            sre_enable_action_on_mmap = "2"
            extend_interrupt_range_support = "1"
        else:
            has_aarch64 = "0"
            vmsa_supported = "0"
            sre_enable_action_on_mmap = "0"
            extend_interrupt_range_support = "0"

        guest_specs = self._normalize_guest_specs(guests_bins, interrupt_flags)

        vm_data_args = []
        for spec in guest_specs:
            vm_data_args.extend(["--data", spec])

        uart_args = []
        for uart_idx in [0, 1, 2]:
            uart_args.extend([
                "-C", f"bp.pl011_uart{uart_idx}.uart_enable=1",
            ])

        cmd = [
            fvp_bin,
            "-C", "gic_distributor.has-two-security-states=0",
            "-C", "cluster0.gicv3.cpuintf-mmap-access-level=2",
            "-C", "cluster0.gicv3.SRE-EL2-enable-RAO=1",
            "-C", f"cluster0.has_aarch64={has_aarch64}",
            "-C", f"cluster0.VMSA_supported={vmsa_supported}",
            "-C", f"cluster0.gicv3.SRE-enable-action-on-mmap={sre_enable_action_on_mmap}",
            "-C", f"cluster0.gicv3.extended-interrupt-range-support={extend_interrupt_range_support}",
            "-C", "bp.smsc_91c111.enabled=true",
            "-C", "bp.hostbridge.userNetworking=true",
            "-C", "bp.hostbridge.userNetSubnet=192.168.42.0/24",
            "-C", "bp.hostbridge.userNetPorts=127.0.0.1:5555=22",
            "--data", f"{run_bin}@0x0",
        ] + uart_args + vm_data_args

        print_log("INFO", f"Launching FVP BaseR from: {fvp_bin}", tab_level=0)
        print_log("INFO", f"Framework UART endpoint: {serial_ports[0]}", tab_level=1)

        fvp_log = tempfile.NamedTemporaryFile(delete=False)
        fvp_log_path = fvp_log.name
        fvp_log.close()

        logf = open(fvp_log_path, "w", encoding="utf-8")

        proc = subprocess.Popen(
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            text=True,
            preexec_fn=os.setsid,
        )

        return proc, fvp_log_path, logf, serial_ports