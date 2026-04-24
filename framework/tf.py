from asyncio import threads
from inputs import CLI
import os
import sys
import time
import yaml
import shutil
import subprocess
import logger
import psutil
import importlib.util
import re

# Root path anchors
CUR_DIR         = os.getcwd()

TF_DIR          = os.path.dirname(os.path.abspath(__file__))            # tests/tf/framework/
TF_FW_DIR       = os.path.join(TF_DIR, "firmware")                      # tests/tf/framework/firmware
TF_GUEST_DIR    = os.path.join(TF_DIR, "guests")                        # tests/tf/framework/guests/
TF_HYP_DIR      = os.path.join(TF_DIR, "hypervisor")                    # tests/tf/framework/hypervisor
TF_PLAT_DIR     = os.path.join(TF_DIR, "platforms")                     # tests/tf/framework/platforms/
TF_TOOL_DIR     = os.path.join(TF_DIR, "toolchains")                    # tests/tf/framework/toolchains/
TF_UTILS_DIR    = os.path.join(TF_DIR, "utils")                         # tests/tf/framework/utils/

TF_ROOT         = os.path.abspath(os.path.join(TF_DIR, "../"))          # tests/tf/
TESTS_DIR       = os.path.abspath(os.path.join(TF_ROOT, "../tests"))   # tests/tests
BENCHS_DIR      = os.path.abspath(os.path.join(TF_ROOT, "../benchs"))  # tests/benchs
HYPERVISOR_DIR  = os.path.abspath(os.path.join(TF_ROOT, "../../"))     # bao-hypervisor/

# Load each module/class to system path
sys.path.append(TF_DIR)
sys.path.append(TF_FW_DIR)
sys.path.append(TF_GUEST_DIR)
sys.path.append(TF_HYP_DIR)
sys.path.append(TF_PLAT_DIR)
sys.path.append(TF_TOOL_DIR)
sys.path.append(TF_UTILS_DIR)

# Test Framework imports
from constants import print_log
from bao import bao
from generic import standalone
from baremetal  import baremetal_test

# Optionally register benchmark guest if the bao-benchmarks submodule is populated
# if os.path.exists(BENCHS_DIR) and os.listdir(BENCHS_DIR):
#     sys.path.append(os.path.join(BENCHS_DIR, "guests"))
#     from baremetal_benchmark import baremetal_benchmark
#     dict_guests["baremetal_benchmark"] = baremetal_benchmark

class test_framework:
    def __init__(self, wrkdir):
        self.wrkdir = wrkdir
        self.list_obj = []
        self.test_cfg = {}
        self.bench_cfg = {}
        self.runtime_config = {}
        self.tests = []
        self.plats = []

    def build_guests(self, platform):

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

        for guest in self.guests:
            print_log("INFO", f"Building guest {guest}:", tab_level=1)

            # if self.run_type == "benchmarks":
            #     guest_type = "baremetal_benchmark"
            #     guest_name = guest[list(guest.keys())[0]][0]['bin_name']
            #     platform_flags = get_platform_build_flags(
            #         guest[list(guest.keys())[0]][1].get('flags', ""),
            #         self.test_config['platform']
            #     )
            #     building_flags = platform_flags["generic_flags"]

            #     #add run_mode to building flags
            #     if self.hypervisor == "standalone":
            #         building_flags = f"{building_flags} STANDALONE=y".strip()

            # else:
            #guest_type = list(guest.keys())[0]
            print("guest_type:", guest)  # Debug print to check guest_type value
            input("Check guest_type value. Press Enter to continue...")  # Pause for inspection
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
                tf_dir = TF_DIR,
                tests_srcs=TESTS_DIR,
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

    def populate_tests(self):
        src_dir = os.path.join(TESTS_DIR, "src")
        self.tests = []

        c_files = sorted(f for f in os.listdir(src_dir) if f.endswith(".c"))
        for suite_nr, fname in enumerate(c_files, start=1):
            with open(os.path.join(src_dir, fname)) as f:
                content = f.read()

            for test_nr, match in enumerate(re.finditer(r'BAO_TEST\s*\(([^)]+)\)', content)):
                args = [a.strip().strip('"') for a in match.group(1).split(",")]
                self.tests.append({
                    'id':          suite_nr * 100 + test_nr,
                    'suite_nr':    suite_nr,
                    'test_nr':     test_nr,
                    'suite':       args[0] if len(args) > 0 else "",
                    'name':        args[1] if len(args) > 1 else "",
                    'setup':       args[2] if len(args) > 2 else "",
                    'guests':      args[2].split('+') if len(args) > 2 else [],
                    'description': args[3] if len(args) > 3 else "",
                    'file':        fname,
                })

        # print(self.tests)
        # input("Populated tests from source files. Press Enter to continue...")

        return self.tests

    def populate_plats(self):
        self.plats = []

        skip = {"generic_platform.py"}

        print_log("INFO", "Loading platform libs...", tab_level=1)
        for fname in os.listdir(TF_PLAT_DIR):
            if not fname.endswith(".py") or fname in skip:
                continue
            stem = fname[:-3]
            class_n = stem.replace("-", "_")
            fpath = os.path.join(TF_PLAT_DIR, fname)

            spec = importlib.util.spec_from_file_location(class_n, fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            self.plats.append((stem, getattr(mod, class_n)))

        # Load generic platform for shared utilities
        fpath = os.path.join(TF_PLAT_DIR, "generic_platform.py")
        spec = importlib.util.spec_from_file_location("generic_platform", fpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    def populate_guests(self):
        self.guests = []

        for test in self.tests:
            for guest in test['guests']:
                if guest not in self.guests:
                    self.guests.append(guest)

        return self.guests

    def validate_tests(self, test_ids):
        valid_ids = {test['id'] for test in self.tests}
        for test_id in test_ids:
            if test_id not in valid_ids:
                raise ValueError(f"Invalid test ID: {test_id}. Valid IDs are: {sorted(valid_ids)}")

    def parse_args(self):
        args = CLI().tf_config(platforms=[plat[0] for plat in self.plats])

        all_ids = [t['id'] for t in self.tests]
        tests_to_run = []
        if args.test is not None and args.test != "all":
            tests_to_run = [int(t) for t in args.test]
        elif args.test_exclude:
            exclude_ids = {int(t) for t in args.test_exclude}
            tests_to_run = [i for i in all_ids if i not in exclude_ids]
        else:
            tests_to_run = all_ids

        print_log("INFO", "Validating tests IDs...", tab_level=0)
        self.validate_tests(tests_to_run)
        print_log("SUCCESS", "Tests to run: {}.".format(", ".join(map(str, tests_to_run))), tab_level=0)

        # Create new variable to hold the full information of the validated tests
        self.tests_to_run = [test for test in self.tests if test['id'] in tests_to_run]

        self.runtime_config = {
            'log_level': int(args.log_level),
            'echo': args.echo,
            'platform': args.platform,
            'platform_args': args.plat_virt_args,
            'firmware_build': not args.no_firmware_build,
            'toolchain_build': not args.no_toolchain_build,
            'hypervisor': args.hypervisor,
            'hypervisor_srcs': args.hyp_srcs,
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

def launch_tests(tf, tests, plat, rt_cfg, wrkdir):

    # Iterate over tests to run and execute them
    for test in tests:
        print_log("INFO", f"Preparing Test ID {test['id']}: {test['suite']} - {test['name']}...", tab_level=0)

        print_log("INFO", f"T{test['id']}: Building guests ...", tab_level=0)
        tf.build_guests(plat)

    print_log("INFO", f"Building run image [{tf.hypervisor}]...", tab_level=0)
    run_bin, bin_name, elf_name = tf.build_run_bin(wrkdir, bao_cfg_path_abs, plat)

    if tf.build_firmware:
        platform.build_firmware(run_bin, interrupt_flags)

    tf.launch_test(run_bin, interrupt_flags, tf.test_config['setup'], tf.test_config['echo'], platform)

def main():
    print_log("INFO", "Starting test framework...", tab_level=0)
    print_log("INFO", f"Current working directory: {CUR_DIR}", tab_level=1)
    wrkdir = os.path.join(CUR_DIR, "wrkdir")
    os.makedirs(wrkdir, exist_ok=True)

    tf = test_framework(wrkdir)

    print_log("INFO", "Populating tests ...", tab_level=0)
    tests = tf.populate_tests()
    print_log("SUCCESS", "Tests populated.", tab_level=0)

    print_log("INFO", "Populating platforms ...", tab_level=0)
    tf.populate_plats()
    print_log("SUCCESS", f"Platforms populated: {', '.join([plat[0] for plat in tf.plats])}.", tab_level=0)

    print_log("INFO", "Populating guests to build ...", tab_level=0)
    guests = tf.populate_guests()
    print_log("SUCCESS", f"Guests populated: {', '.join(guests)}.", tab_level=0)

    print_log("INFO", "Reading TF configuration ...", tab_level=0)
    tf.parse_args()
    print_log("SUCCESS", "Runtime TF configuration built.", tab_level=0)

    print_log("INFO", "Cleaning up build artifacts from previous runs...", tab_level=0)
    tf.cleanup()

    print_log("INFO", "Setting up platform...", tab_level=0)
    plat = dict(tf.plats)[tf.runtime_config['platform']](wrkdir)
    plat.setup_platform()

    if tf.runtime_config['toolchain_build']:
        plat.build_toolchain()
    else:
        plat.toolchain = plat.toolchain_prefix
        print_log("INFO", f"Skipping toolchain build, expecting '{plat.toolchain_prefix}' to be available in the environment.", tab_level=1)

    print_log("INFO", "Preparing to launch test IDs {} on platform {}...".format([test['id'] for test in tests], tf.runtime_config['platform']), tab_level=0)
    launch_tests(tf, tests, plat, tf.runtime_config, wrkdir)

    tf.cleanup()

if __name__ == "__main__":
    main()
