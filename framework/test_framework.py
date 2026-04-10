import argparse
from asyncio import threads
import os
import sys
import time
import yaml
import shutil
import subprocess
import logger
import psutil

# Root path anchors
CUR_DIR        = os.path.dirname(os.path.abspath(__file__))
TF_DIR         = CUR_DIR                                                # tests/tf/framework/
TF_ROOT        = os.path.abspath(os.path.join(CUR_DIR, "../"))          # tests/tf/
TESTS_DIR      = os.path.abspath(os.path.join(CUR_DIR, "../../tests"))  # tests/tests
BENCHS_DIR     = os.path.abspath(os.path.join(CUR_DIR, "../../benchs")) # tests/benchs
HYPERVISOR_DIR = os.path.abspath(os.path.join(CUR_DIR, "../../../"))    # bao-hypervisor/

# Test Framework imports
sys.path.append(TF_ROOT)
from constants import print_log

sys.path.append(os.path.join(TF_DIR, "hypervisor"))
from bao import bao
from generic import standalone

sys.path.append(os.path.join(TF_DIR, "platforms"))
from qemu_aarch64_virt import qemu_aarch64_virt
from qemu_riscv64_virt import qemu_riscv64_virt
from tc4dx import tc4dx
from zcu104 import zcu104
from s32z270 import s32z270
from rh850 import rh850
from fvp_r import fvp_r

sys.path.append(os.path.join(TF_DIR, "guests"))
from baremetal  import baremetal_test

dict_platforms = {
    "qemu-aarch64-virt": qemu_aarch64_virt,
    "qemu-riscv64-virt": qemu_riscv64_virt,
    "fvp-r": fvp_r,
    "tc4dx": tc4dx,
    "s32z270": s32z270,
    "rh850-u2a16" : rh850,
    "zcu104": zcu104
}

dict_guests = {
    "baremetal" : baremetal_test,
}

# Optionally register benchmark guest if the bao-benchmarks submodule is populated
if os.path.exists(BENCHS_DIR) and os.listdir(BENCHS_DIR):
    sys.path.append(os.path.join(BENCHS_DIR, "guests"))
    from baremetal_benchmark import baremetal_benchmark
    dict_guests["baremetal_benchmark"] = baremetal_benchmark

class test_framework:
    def __init__(self, wrkdir):
        self.wrkdir = wrkdir
        self.tests_srcs = TESTS_DIR
        self.bao_tests_dir = TF_ROOT
        self.bao_hypervisor_dir = HYPERVISOR_DIR
        self.disable_logger = False
        self.list_obj = []

    def build_guests(self, platform, interrupt_flags):

        def normalize_guest_flags(flags_entry):
            if isinstance(flags_entry, dict):
                generic_flags = flags_entry.get("generic_flags", "")
                if generic_flags is None:
                    generic_flags = ""
                elif not isinstance(generic_flags, str):
                    generic_flags = str(generic_flags)

                return {
                    "generic_flags": generic_flags,
                    "cpu_num": flags_entry.get("cpu_num"),
                }

            if isinstance(flags_entry, str):
                return {
                    "generic_flags": flags_entry,
                    "cpu_num": None,
                }

            return {
                "generic_flags": "",
                "cpu_num": None,
            }

        def get_platform_build_flags(flags_cfg, platform_name):
            if isinstance(flags_cfg, dict):
                if "generic_flags" in flags_cfg or "cpu_num" in flags_cfg:
                    return normalize_guest_flags(flags_cfg)
                return normalize_guest_flags(flags_cfg.get(platform_name))

            if isinstance(flags_cfg, list):
                for item in flags_cfg:
                    if isinstance(item, dict) and platform_name in item:
                        return normalize_guest_flags(item[platform_name])
                return normalize_guest_flags("")

            return normalize_guest_flags(flags_cfg)

        for guest in self.test_config['guests']:
            print_log("INFO", f"Building guest:", tab_level=1)

            if self.run_type == "benchmarks":
                guest_type = "baremetal_benchmark"
                guest_name = guest[list(guest.keys())[0]][0]['bin_name']
                platform_flags = get_platform_build_flags(
                    guest[list(guest.keys())[0]][1].get('flags', ""),
                    self.test_config['platform']
                )
                building_flags = platform_flags["generic_flags"]

                #add run_mode to building flags
                if self.hypervisor == "standalone":
                    building_flags = f"{building_flags} STANDALONE=y".strip()

            else:
                guest_type = list(guest.keys())[0]
                guest_name = guest[guest_type][0]['bin_name']
                building_flags = get_platform_build_flags(
                    guest[guest_type][1].get('flags', {}),
                    self.test_config['platform']
                )

            print_log("INFO", f"Building guest_type: {guest_type}", tab_level=2)
            print_log("INFO", f"Building bin_name: {guest_name}", tab_level=2)
            print_log("INFO", f"Building flags: {building_flags}", tab_level=2)

            bin_name=guest_name
            flags=building_flags

            guest_class = dict_guests.get(guest_type)

            list_tests = self.test_config["tests"]
            list_suites = self.test_config["suites"]
            benchmark = self.test_config["benchmark"]

            guest_instance = guest_class(
                self.wrkdir, list_tests, list_suites, benchmark,
                tests_srcs=self.tests_srcs,
                bao_tests_path=self.bao_tests_dir,
                bin_name = bin_name,
                build_flags = flags
            )

            self.list_obj.append(guest_instance)

            guest_instance.build(
                platform=self.test_config['platform'],
                arch=platform.architecture,
                toolchain=platform.toolchain,
                irq_flags=interrupt_flags
                )

    def run_cmd(self, cmd, cwd=None):
        p = subprocess.run(cmd, cwd=cwd, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")



    def build_run_bin(self, wrkdir, config_path, platform):

        wrkdir_abs = os.path.abspath(wrkdir)

        guests_build_dir = os.path.join(wrkdir_abs, "guests", "build")
        platform_name = self.test_config['platform']

        env = os.environ.copy()
        env["ARCH"] = platform.architecture
        env["CROSS_COMPILE"] = f"{platform.toolchain}"

        hypervisor_dict = {
            "bao" : bao,
            "standalone" : standalone
        }

        hypervisor_class = hypervisor_dict.get(self.hypervisor)
        hypervisor_instance = hypervisor_class()

        hypervisor_instance.fetch_sources(self.hypervisor_srcs)
        hypervisor_instance.clean(hypervisor_instance.srcs_path)

        out_bin_path, bin_name, elf_name = hypervisor_instance.build(
            wrkdir_imgs=guests_build_dir,
            config_repo=config_path,
            config_name=platform_name,
            platform=platform_name,
            env=env
        )

        print_log("SUCCESS", f"Successfully built final image!", tab_level=1)
        return out_bin_path, bin_name, elf_name

    def clean_build_artifacts(self):
        #ToDo: implement build artifact cleanup process
        pass

    def parse_args(self):
        """
        Parse python script arguments.
        """
        parser = argparse.ArgumentParser(description="Bao Testing Framework")

        parser.add_argument("-log_level", "--log_level",
                    help="Allows to define the amount of information produced"
                         "by the framework: "
                         "0 - only logs the final report, "
                         "1 - logs failed tests and the final report, "
                         "2 - logs all test results and the final report",
                    default=0)

        parser.add_argument("-echo", "--echo",
                    help="Allows to define the filtering of the framework: "
                         "full - does not filter any information"
                         "tf - filters logging not produced by the framework"
                         "none - filter every logging",
                    default="tf")

        parser.add_argument("-platform", "--platform",
                    help="Used define the target platform",
                    default=" ")

        parser.add_argument("-gicv", "--gicv",
                    required=False,
                    help="Used to define the GIC version setup for the platform",
                    default="")

        parser.add_argument("-irqc", "--irqc",
                        required=False,
                        help="Used to define the IRQ controller setup for the platform",
                        default="")

        parser.add_argument("-ipic", "--ipic",
                        required=False,
                        help="Used to define the IPIC setup for the platform",
                        default="")

        parser.add_argument("-test", "--test",
                    help="Name of default test to be executed",
                    default=" ")

        parser.add_argument("-setup", "--setup",
                    help="Target setup (e.g., baremetal freertos)",
                    default=" ")

        parser.add_argument("--no_logger", action="store_true",
                    help="Disables logging functionality",
                    default=False)

        parser.add_argument("-benchmark", "--benchmark",
                    help="Used to define if the test execution is for benchmark purposes, which may impact the logging and reporting behavior of the framework",
                    default=" ")
        parser.add_argument("--no_firmware_build", action="store_true",
                    help="Skips firmware build phase, assuming pre-built firmware is available. This can be useful for development iterations when firmware changes are not needed.",
                    default=False)

        parser.add_argument("--no_toolchain_build", action="store_true",
                    help="Skips toolchain download/build phase. The toolchain is expected to be available in the system PATH.",
                    default=False)

        parser.add_argument("-hypervisor", "--hypervisor",
                        required=False,
                        help="Used to define if the Bao hypervisor build phase should be skipped, assuming a pre-built hypervisor binary is available. This can be useful for development iterations when hypervisor changes are not needed.",
                        default="bao")

        parser.add_argument("--hypervisor_srcs",
                            required=False,
                            help="Path to Bao hypervisor sources. If not provided, the framework will attempt to fetch the sources from the official repository.",
                            default="")


        # either "config" or "test" and "setup" must be provided
        args = parser.parse_args()

        test_config = {}

        irq_flags = {}
        if args.gicv != "":
            irq_flags = {'GIC_version': args.gicv}
        else:
            if args.irqc != "":
                irq_flags = {'IRQ_controller': args.irqc}
            if args.ipic != "":
                irq_flags = {'IPIC': args.ipic}

        config_file = os.path.abspath(os.path.join(CUR_DIR, "test_config.yaml"))

        def read_config(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f)

        def resolve_setup_guests(setups_cfg, setup_name):
            def is_guest_attr_list(value):
                return (
                    isinstance(value, list)
                    and all(isinstance(item, dict) for item in value)
                    and any(("bin_name" in item or "flags" in item) for item in value)
                )

            def as_guest_list(found_key, found_value):
                if is_guest_attr_list(found_value):
                    return [{found_key: found_value}]
                if isinstance(found_value, list):
                    return found_value
                return []

            if isinstance(setups_cfg, dict):
                if setup_name in setups_cfg:
                    return as_guest_list(setup_name, setups_cfg[setup_name])

                for setup_map in setups_cfg.values():
                    if not isinstance(setup_map, dict):
                        continue
                    if setup_name in setup_map:
                        return as_guest_list(setup_name, setup_map[setup_name])
                    for nested_setups in setup_map.values():
                        if not isinstance(nested_setups, list):
                            continue
                        for nested_setup in nested_setups:
                            if isinstance(nested_setup, dict) and setup_name in nested_setup:
                                return as_guest_list(setup_name, nested_setup[setup_name])
                return []

            if isinstance(setups_cfg, list):
                for setup_entry in setups_cfg:
                    if isinstance(setup_entry, dict) and setup_name in setup_entry:
                        return as_guest_list(setup_name, setup_entry[setup_name])

                for setup_entry in setups_cfg:
                    if not isinstance(setup_entry, dict):
                        continue
                    for nested_setups in setup_entry.values():
                        if not isinstance(nested_setups, list):
                            continue
                        for nested_setup in nested_setups:
                            if isinstance(nested_setup, dict) and setup_name in nested_setup:
                                return as_guest_list(setup_name, nested_setup[setup_name])
                return []

            return []


        list_tests = ""
        list_suites = ""
        list_guests = {}

        self.run_type = None

        # parse tests file
        if args.test.strip():
            self.run_type = "tests"
            config_file = os.path.abspath(os.path.join(TESTS_DIR, "tests_config.yaml"))

            test_config = read_config(config_file) if os.path.exists(config_file) else {}
            test_config = test_config or {}

            list_guests = resolve_setup_guests(test_config.get("setups", {}), args.setup)

            tests_cfg = test_config.get("tests", {})
            test_entry = tests_cfg.get(args.test, [])

            list_tests = test_entry[0].get("list_tests", "") if len(test_entry) > 0 else ""
            list_suites = test_entry[1].get("list_suites", "") if len(test_entry) > 1 else ""

        # parse benchmark file
        if args.benchmark != " ":
            self.run_type = "benchmarks"
            config_file = os.path.abspath(os.path.join(BENCHS_DIR, "benchmarks_config.yaml"))
            test_config = read_config(config_file)
            list_setups = test_config.get("benchmarks", {})
            for setup in list_setups:
                if args.benchmark in setup:
                    list_guests = setup[args.benchmark]
                    break


        bao_config_path = ""
        if self.run_type == "benchmarks":
            bao_config_path = os.path.join(BENCHS_DIR, "configs", args.benchmark)
        elif self.run_type == "tests":
            bao_config_path = os.path.join(TESTS_DIR, "configs", args.setup)
        else:
            bao_config_path = ""

        self.build_firmware = not args.no_firmware_build
        self.build_toolchain = not args.no_toolchain_build
        self.hypervisor = args.hypervisor
        self.hypervisor_srcs = args.hypervisor_srcs

        self.test_config = {
            'log_level': int(args.log_level),
            'echo': args.echo,
            'platform': args.platform,
            'irq_flags': irq_flags,
            'guests': list_guests,
            'tests': list_tests,
            'suites': list_suites,
            'bao_config': bao_config_path,
            'setup': args.setup,
            'benchmark' : args.benchmark
        }

    def launch_test(self, run_bin, irq_flags, setup, echo, platform):
        logger_inst = logger.TestLogger(platform.cpu_freq, platform.timer_freq)

        guests_bins = os.path.join(self.wrkdir, "guests", "build")

        if platform.is_emulated:
            try:
                proc, stderr_path, errf, serial_ports = platform.launch_test(
                    run_bin, irq_flags, guests_bins, setup, self.hypervisor
                )
                # time.sleep(1)

                if proc.poll() is not None:
                    raise RuntimeError("QEMU died before serial connection")
                log_threads = logger_inst.connect_to_platform_port(serial_ports, echo, self.run_type == "benchmarks")

                logger_inst.wait_for_finish(log_threads)

                if proc != None:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except Exception:
                        proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        except Exception:
                            proc.kill()
                        proc.wait(timeout=5)
            finally:
                platform_cleanup = getattr(platform, "cleanup", None)
                if callable(platform_cleanup):
                    platform_cleanup()

        else:
            serial_ports = platform.get_serial_ports()
            log_threads = logger_inst.connect_to_platform_port(serial_ports, echo, self.run_type == "benchmarks")
            proc = platform.launch_test(
                run_bin, irq_flags, guests_bins, setup, self.hypervisor
            )

            logger_inst.wait_for_finish(log_threads)

            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

            if proc.returncode != 0:
                err = proc.stderr.read() if proc.stderr else ""
                raise Exception(f"Command failed: {err}")

        if not serial_ports:
            print("[INFO] No serial ports returned by platform. Skipping logger and cleanup.")
            return


    def cleanup(self):
        guests_dir = os.path.join(CUR_DIR, "wrkdir", "guests")
        if os.path.exists(guests_dir):
            print("removing guests build artifacts at:", guests_dir)
            shutil.rmtree(guests_dir)


def main():
    wrkdir = os.path.join(os.getcwd(), "wrkdir")
    os.makedirs(wrkdir, exist_ok=True)

    tf = test_framework(wrkdir)

    print_log("INFO", "Parsing test configuration...", tab_level=0)
    tf.parse_args()
    print_log("SUCCESS", "Parsed test configuration.", tab_level=0)

    bao_cfg_path_abs = os.path.abspath(tf.test_config['bao_config'])
    tf.cleanup()

    print_log("INFO", "Setting up platform...", tab_level=0)
    platform_class = dict_platforms.get(tf.test_config['platform'])
    platform = platform_class(wrkdir)
    platform.setup_platform()
    if tf.build_toolchain:
        platform.build_toolchain()
    else:
        platform.toolchain = platform.toolchain_prefix
        print_log("INFO", f"Skipping toolchain build, expecting '{platform.toolchain_prefix}' to be available in the environment.", tab_level=1)

    interrupt_flags = tf.test_config['irq_flags'] or platform.irq_flags

    print_log("INFO", "Building guests...", tab_level=0)
    tf.build_guests(platform, interrupt_flags)

    print_log("INFO", f"Building run image [{tf.hypervisor}]...", tab_level=0)
    run_bin, bin_name, elf_name = tf.build_run_bin(wrkdir, bao_cfg_path_abs, platform)

    if tf.build_firmware:
        platform.build_firmware(run_bin, interrupt_flags)

    tf.launch_test(run_bin, interrupt_flags, tf.test_config['setup'], tf.test_config['echo'], platform)
    tf.cleanup()


if __name__ == "__main__":
    main()
