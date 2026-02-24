import argparse
import os
import sys
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

cur_dir = os.path.dirname(os.path.abspath(__file__))

class test_framework:
    def __init__(self, wkrdir):
        self.tests_srcs = os.path.abspath(os.path.join(cur_dir, "../src/tests"))
        self.bao_tests_dir = os.path.abspath(os.path.join(cur_dir, "../../bao-tests"))
        self.bao_hypervisor_dir = os.path.abspath(os.path.join(cur_dir, "../../../"))
        self.disable_logger = False

    def build_guests(self, platform):

        for guest in self.test_config['guests']:
            print_log("INFO", f"Building guest:", tab_level=1)

            def get_platform_build_flags(list_flags, platform_name, guest_name):
                for flags in list_flags:
                    if platform_name in flags:
                        return flags[platform_name]
                return ""
                

            if self.run_type == "benchmark":
                guest_type = "baremetal_benchmark"
                guest_name = guest[list(guest.keys())[0]][0]['bin_name']
                building_flags = get_platform_build_flags(
                    guest[list(guest.keys())[0]][1]['flags'],
                    self.test_config['platform'],
                    guest_name
                )
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

            # get absolute path of current directory
            cur_dir = os.getcwd()
            tests_srcs_dir = os.path.realpath(
                os.path.join(cur_dir, self.tests_srcs)
            )

            bao_tests_dir = os.path.realpath(
                os.path.join(cur_dir, self.bao_tests_dir)
            )
            guest_instance = guest_class(
                wrkdir, list_tests, list_suites, benchmark,
                tests_srcs=tests_srcs_dir,
                bao_tests_path=bao_tests_dir,
                bin_name = bin_name,
                build_flags = flags
            )

            guest_instance.build(
                platform=self.test_config['platform'],
                arch=platform.architecture,
                toolchain=platform.toolchain,
                irq_flags=interrupt_flags
                )

    def run_cmd(self, cmd, cwd=None):
        # print(f"[CMD] {' '.join(cmd)}")
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    
    def build_hypervisor(self, wrkdir, bao_config_path, platform, irq_flags):
        # Resolve paths
        bao_srcs_path = os.path.abspath(self.bao_hypervisor_dir)
        wrkdir_abs = os.path.abspath(wrkdir)

        # Create an $out-like directory inside bao_hypervisor_dir
        out_dir = os.path.join(bao_srcs_path, "bao_imgs")

        print_log("INFO", "Setting up Bao hypervisor build environment...", tab_level=1)
        # print("[INFO]    bao_srcs_path :", bao_srcs_path)
        # print("[INFO]    wrkdir_abs    :", wrkdir_abs)
        # print("[INFO]    out_dir       :", out_dir)
        # print("[INFO]    bao_config_path:", bao_config_path)

        guests_build_dir = os.path.join(wrkdir_abs, "guests", "build")
        platform_name = self.test_config['platform']

        env = os.environ.copy()
        env["ARCH"] = platform.architecture
        env["CROSS_COMPILE"] = f"{platform.toolchain}-"
        
        make_cmd = [
            "make",
            f"PLATFORM={platform_name}",
            f"CONFIG_REPO={bao_config_path}",
            f"CONFIG={platform_name}",
            f"CPPFLAGS=-DBAO_WRKDIR_IMGS={guests_build_dir}"
        ]

        if platform.architecture == "aarch64" and irq_flags:
            gic_version = irq_flags.get("GIC_version", "GICV2")
            make_cmd.append(f"GIC_VERSION={gic_version}")

        # print("[CMD] " + " ".join(make_cmd))

        # Run make in the hypervisor source dir (../../../)
        self.run_cmd(make_cmd, cwd=bao_srcs_path)

        bao_bin_path = os.path.join(
            bao_srcs_path, "bin", platform_name, platform_name, "bao.bin"
        )

        print_log("SUCCESS", f"Successfully built Bao hypervisor!", tab_level=1)
        return bao_bin_path

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
        
        # either "config" or "test" and "setup" must be provided
        args = parser.parse_args()
        
        test_config = {}
        # if all fields of gicv, irqc, ipic were not provided, return error
        if args.gicv == "" and args.irqc == "" and args.ipic == "":
            parser.error("At least one of --gicv, --irqc or --ipic must be provided when using --test and --setup.")

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
            self.run_type = "test"
            config_file = os.path.abspath(os.path.join(cur_dir, "test_config.yaml"))
            test_config = read_config(config_file)
            tests_lists = test_config.get("tests", {}).get(args.setup, {})
            list_tests = tests_lists.get(args.test, [{}])[0].get("list_tests", "")
            list_suites = tests_lists.get(args.test, [{}])[1].get("list_suites", "")

            list_setups = test_config.get("setups", {}).get("test", {})
            list_guests = list_setups.get(args.setup, {})

        # parse benchmark file
        if args.benchmark != " ":
            self.run_type = "benchmark"
            config_file = os.path.abspath(os.path.join(cur_dir, "benchmarks_config.yaml"))
            test_config = read_config(config_file)
            list_setups = test_config.get("benchmarks", {})
            for setup in list_setups:
                if args.benchmark in setup:
                    list_guests = setup[args.benchmark]
                    break
        

        bao_config_path = os.path.abspath(os.path.join(cur_dir, f"tests_configurations"))

        if self.run_type is not None:
            if self.run_type == "test":
                bao_config_path = os.path.join(bao_config_path, "tests", args.setup)
            elif self.run_type == "benchmark":
                bao_config_path = os.path.join(bao_config_path, "benchmarks", args.benchmark)



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

    def launch_test(self, bao_bin, irq_flags, setup, echo):
        logger_inst = logger.TestLogger()

        proc, stderr_path, errf, serial_ports = platform.launch_test(
            bao_bin, irq_flags, setup
        )

        # Safety valve: platform launch not fully implemented (e.g. tc4dx)
        if not serial_ports:
            print("[INFO] No serial ports returned by platform. Skipping logger and cleanup.")
            return

        logger_inst.connect_to_platform_port(serial_ports, echo)

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


sys.path.append(os.path.abspath(os.path.join(cur_dir, "platforms")))
from qemu_aarch64_virt import qemu_aarch64_virt
from tc4dx import tc4dx

sys.path.append(os.path.abspath(os.path.join(cur_dir, "guests")))
from baremetal import baremetal_test, baremetal_benchmark
# from baremetal_benchmark import baremetal_benchmark
from s32 import s32
from rh850 import rh850

dict_platforms = {
    "qemu-aarch64-virt": qemu_aarch64_virt,
    "tc4dx": tc4dx,
    "s32": s32,
    "rh850-u2a16" : rh850,
    # "qemu-riscv64-virt": qemu_riscv64_virt
}

dict_guests = {
    "baremetal" : baremetal_test,
    "baremetal_benchmark" : baremetal_benchmark
}

if __name__ == "__main__":
    wrkdir = os.getcwd()
    wrkdir += "/wrkdir"
    if not os.path.exists(wrkdir):
        os.makedirs(wrkdir)

    tf = test_framework(wrkdir)
    print_log("INFO", f"Parsing test configuration...", tab_level=0)
    tf.parse_args()
    print_log("SUCCESS", f"Parsed test configuration.", tab_level=0)

    interrupt_flags = tf.test_config['irq_flags']
    bao_cfg_path_abs = os.path.abspath(tf.test_config['bao_config'])

    print_log("INFO", f"Setting up platform...", tab_level=0)
    platform_class = dict_platforms.get(tf.test_config['platform'])
    platform = platform_class(wrkdir)
    platform.setup_platform()
    print_log("INFO", f"Building firmware...", tab_level=1)
    platform.build_firmware(interrupt_flags)

    print_log("INFO", f"Building guests...", tab_level=0)
    tf.build_guests(platform)

    print_log("INFO", f"Building Bao hypervisor...", tab_level=0)
    bao_bin = tf.build_hypervisor(
        wrkdir,
        bao_cfg_path_abs,
        platform,
        interrupt_flags
    )

    tf.launch_test(bao_bin, interrupt_flags, tf.test_config['setup'], tf.test_config['echo'])
