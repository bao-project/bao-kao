import argparse
from asyncio import threads
import os
import sys
import time
import yaml
import shutil
import subprocess
import logger
import subprocess
import psutil
from constants import print_log
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

sys.path.append(os.path.abspath(os.path.join(cur_dir, "hypervisor")))
from bao import bao
from generic import standalone


sys.path.append(os.path.abspath(os.path.join(cur_dir, "platforms")))
from qemu_aarch64_virt import qemu_aarch64_virt
from tc4dx import tc4dx
from zcu104 import zcu104
from s32z270 import s32z270
from rh850 import rh850

sys.path.append(os.path.abspath(os.path.join(cur_dir, "guests")))
from baremetal import baremetal_test

dict_platforms = {
    "qemu-aarch64-virt": qemu_aarch64_virt,
    "tc4dx": tc4dx,
    "s32z270": s32z270,
    "rh850-u2a16" : rh850,
    "zcu104": zcu104
}

dict_guests = {
    "baremetal" : baremetal_test,
}

benchmarks_path = os.path.abspath(os.path.join(cur_dir, "../../bao-benchmarks"))
IS_BENCHMARKS_AVAILABLE = False
if os.path.exists(benchmarks_path) and os.listdir(benchmarks_path):
    IS_BENCHMARKS_AVAILABLE = True
    sys.path.append(os.path.abspath(os.path.join(benchmarks_path, "guests")))
    from baremetal_benchmark import baremetal_benchmark
    dict_guests["baremetal_benchmark"] = baremetal_benchmark

class test_framework:
    def __init__(self, wkrdir):
        self.tests_srcs = os.path.abspath(os.path.join(cur_dir, "../../tests"))
        self.bao_tests_dir = os.path.abspath(os.path.join(cur_dir, "../tests"))
        self.bao_hypervisor_dir = os.path.abspath(os.path.join(cur_dir, "../../../"))
        self.disable_logger = False
        self.list_obj = []

    def build_guests(self, platform, interrupt_flags):

        for guest in self.test_config['guests']:
            print_log("INFO", f"Building guest:", tab_level=1)

            def get_platform_build_flags(list_flags, platform_name, guest_name):
                for flags in list_flags:
                    if platform_name in flags:
                        return flags[platform_name]
                return ""


            if self.run_type == "benchmarks":
                guest_type = "baremetal_benchmark"
                guest_name = guest[list(guest.keys())[0]][0]['bin_name']
                building_flags = get_platform_build_flags(
                    guest[list(guest.keys())[0]][1]['flags'],
                    self.test_config['platform'],
                    guest_name
                )

                #add run_mode to building flags
                if self.hypervisor == "standalone":
                    building_flags += " STANDALONE=y"

            else:
                guest_type = list(guest.keys())[0]
                guest_name = guest[guest_type][0]['bin_name']
                building_flags = guest[guest_type][1]['flags']

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
                wrkdir, list_tests, list_suites, benchmark,
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

        if os.path.isdir(os.path.join(config_path, platform_name)):
            config_path = os.path.join(config_path, platform_name)

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

        config_file = os.path.abspath(os.path.join(cur_dir, "test_config.yaml"))

        def read_config(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f)


        list_tests = ""
        list_suites = ""
        list_guests = {}

        self.run_type = None

        # parse tests file
        if args.test != " ":
            self.run_type = "tests"
            config_file = os.path.abspath(os.path.join(cur_dir, "test_config.yaml"))
            test_config = read_config(config_file)

            tests_cfg = test_config.get("tests", {})
            test_entry = tests_cfg.get(args.test, [])
            list_tests = test_entry[0].get("list_tests", "") if len(test_entry) > 0 else ""
            list_suites = test_entry[1].get("list_suites", "") if len(test_entry) > 1 else ""

            setups_cfg = test_config.get("setups", {})
            list_guests = {}

            for group_name, setup_map in setups_cfg.items():
                if args.setup in setup_map:
                    list_guests = setup_map[args.setup]
                    break


        # parse benchmark file
        if args.benchmark != " ":
            self.run_type = "benchmarks"
            config_file = os.path.abspath(os.path.join(cur_dir, "benchmarks_config.yaml"))
            test_config = read_config(config_file)
            list_setups = test_config.get("benchmarks", {})
            for setup in list_setups:
                if args.benchmark in setup:
                    list_guests = setup[args.benchmark]
                    break


        bao_config_path = ""
        if self.run_type == "benchmarks":
             bao_config_path = os.path.join(benchmarks_path, "tests_configurations")
        elif self.run_type == "tests":
            bao_config_path = os.path.join(cur_dir, f"../../{self.run_type}/tests_configurations")
        print(f"bao_config_path: {bao_config_path}")

        if self.run_type is not None:
            if self.run_type == "tests":
                bao_config_path = os.path.join(bao_config_path, args.setup)
            elif self.run_type == "benchmarks":
                bao_config_path = os.path.join(bao_config_path, args.benchmark)

        self.build_firmware = not args.no_firmware_build
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

        guests_bins = os.path.join(cur_dir, "wrkdir", "guests", "build")
        guests_bins = os.path.abspath(guests_bins)

        if platform.is_emulated:
            proc, stderr_path, errf, serial_ports = platform.launch_test(
                run_bin, irq_flags, guests_bins, setup, self.hypervisor
            )
            # time.sleep(1)

            if proc.poll() is not None:
                raise RuntimeError("QEMU died before serial connection")
            log_threads = logger_inst.connect_to_platform_port(serial_ports, echo, self.run_type == "benchmarks")

            logger_inst.wait_for_finish(log_threads)

            if proc != None:
                parent = psutil.Process(proc.pid)
                children = parent.children(recursive=True)
                for child in children:
                    try:
                        child.terminate()
                        child.wait()
                    except psutil.NoSuchProcess:
                        pass
                try:
                    parent.terminate()
                    parent.wait()
                except psutil.NoSuchProcess:
                    pass

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
        guests_dir = os.path.join(cur_dir, "wrkdir", "guests")
        if os.path.exists(guests_dir):
            print("removing guests build artifacts at:", guests_dir)
            shutil.rmtree(guests_dir)


if __name__ == "__main__":
    wrkdir = os.getcwd()
    wrkdir += "/wrkdir"
    if not os.path.exists(wrkdir):
        os.makedirs(wrkdir)

    tf = test_framework(wrkdir)
    print_log("INFO", f"Parsing test configuration...", tab_level=0)
    tf.parse_args()
    print_log("SUCCESS", f"Parsed test configuration.", tab_level=0)

    bao_cfg_path_abs = os.path.abspath(tf.test_config['bao_config'])

    tf.cleanup()

    print_log("INFO", f"Setting up platform...", tab_level=0)
    platform_class = dict_platforms.get(tf.test_config['platform'])
    platform = platform_class(wrkdir)
    platform.setup_platform()
    print_log("INFO", f"Building firmware...", tab_level=1)
    platform.build_toolchain()

    if tf.test_config['irq_flags'] == {}:
        interrupt_flags = platform.irq_flags
    else:
        interrupt_flags = tf.test_config['irq_flags']

    print_log("INFO", f"Building guests...", tab_level=0)
    tf.build_guests(platform, interrupt_flags)

    print_log("INFO", f"Building run image [{tf.hypervisor}]...", tab_level=0)
    run_bin, bin_name, elf_name = tf.build_run_bin(
        wrkdir,
        bao_cfg_path_abs,
        platform
    )

    if tf.build_firmware:
        platform.build_firmware(interrupt_flags)

    tf.launch_test(run_bin, interrupt_flags, tf.test_config['setup'], tf.test_config['echo'], platform)
    tf.cleanup()
