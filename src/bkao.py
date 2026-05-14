"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Bao Kao Framework runner and orchestration logic.
"""

import os
import importlib
import importlib.util
import re
import shutil
import signal
import subprocess
import sys

import logger

# pylint: disable=import-error,wrong-import-position
# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# pylint: disable=too-many-arguments,too-many-instance-attributes
# pylint: disable=missing-function-docstring,line-too-long

# Root path anchors
CUR_DIR = os.getcwd()

BKAO_DIR = os.path.dirname(os.path.abspath(__file__))  # tests/tf/src/
BKAO_FW_DIR = os.path.join(BKAO_DIR, "firmware")  # tests/tf/src/firmware
BKAO_GUEST_DIR = os.path.join(BKAO_DIR, "guests")  # tests/tf/src/guests/
BKAO_HYP_DIR = os.path.join(BKAO_DIR, "hypervisor")  # tests/tf/src/hypervisor
BKAO_PLAT_DIR = os.path.join(BKAO_DIR, "platforms")  # tests/tf/src/platforms/
BKAO_TOOL_DIR = os.path.join(BKAO_DIR, "toolchains")  # tests/tf/src/toolchains/
BKAO_UTILS_DIR = os.path.join(BKAO_DIR, "utils")  # tests/tf/src/utils/

BKAO_ROOT = os.path.abspath(os.path.join(BKAO_DIR, "../"))  # tests/tf/
TESTS_DIR = os.path.abspath(os.path.join(BKAO_ROOT, "../tests"))  # tests/tests
BENCHS_DIR = os.path.abspath(os.path.join(BKAO_ROOT, "../benchs"))  # tests/benchs
HYPERVISOR_DIR = os.path.abspath(os.path.join(BKAO_ROOT, "../../"))  # bao-hypervisor/

# Load each module/class to system path
sys.path.append(BKAO_DIR)
sys.path.append(BKAO_FW_DIR)
sys.path.append(BKAO_GUEST_DIR)
sys.path.append(BKAO_HYP_DIR)
sys.path.append(BKAO_PLAT_DIR)
sys.path.append(BKAO_TOOL_DIR)
sys.path.append(BKAO_UTILS_DIR)

BAREMETAL_BENCHMARK = None
if os.path.exists(BENCHS_DIR) and os.listdir(BENCHS_DIR):
    sys.path.append(os.path.join(BENCHS_DIR, "guests"))
    benchmark_module = importlib.import_module("baremetal_benchmark")
    BAREMETAL_BENCHMARK = getattr(benchmark_module, "baremetal_benchmark")

# Bao Kao Framework imports
CLI = getattr(importlib.import_module("inputs"), "CLI")
print_log = getattr(importlib.import_module("constants"), "print_log")
bao = getattr(importlib.import_module("hypervisor.bao.bao"), "bao")
config_renderer_module = importlib.import_module("hypervisor.bao.config_renderer")
read_config = getattr(config_renderer_module, "read_config")
write_config = getattr(config_renderer_module, "write_config")
standalone = getattr(importlib.import_module("hypervisor.generic"), "standalone")
baremetal_test = getattr(importlib.import_module("baremetal"), "baremetal_test")

def _get_platform_name(platform):
    platform_name = getattr(platform, "platform_name", None)
    if platform_name:
        return platform_name
    return platform.__class__.__name__.replace("_", "-")

def _platform_name_candidates(platform_name):
    normalized_name = str(platform_name).strip().lower()
    candidates = [
        normalized_name,
        normalized_name.replace("_", "-"),
        normalized_name.replace("-", "_"),
    ]
    return [
        candidate
        for i, candidate in enumerate(candidates)
        if candidate and candidate not in candidates[:i]
    ]

def _resolve_platform_class(platforms, platform_name):
    platform_lookup = dict(platforms)
    for candidate in _platform_name_candidates(platform_name):
        platform_class = platform_lookup.get(candidate)
        if platform_class is not None:
            return platform_class
    return None

class TestFramework:
    """Encapsulate workload discovery, build and execution flow."""

    def __init__(self, wrkdir):
        self.wrkdir = wrkdir
        self.list_obj = []
        self.test_cfg = {}
        self.bench_cfg = {}
        self.runtime_config = {}
        self.tests = []
        self.benchmarks = []
        self.tests_to_run = []
        self.run_type = "test"
        self.plats = []
        self.test_config = {}
        self.hypervisor = "bao"
        self.hypervisor_srcs = ""
        self.guests = []

    def build_guests(self, platform, irq_flags=None):

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

        def resolve_guest_build_options(build_options_cfg, guest_type, platform_name):
            guest_name = guest_type
            flags_cfg = {}

            if isinstance(build_options_cfg, dict):
                bin_name = build_options_cfg.get("bin_name")
                if isinstance(bin_name, str) and bin_name.strip():
                    guest_name = bin_name

                if "flags" in build_options_cfg:
                    flags_cfg = build_options_cfg.get("flags", {})
                else:
                    flags_cfg = {
                        key: value
                        for key, value in build_options_cfg.items()
                        if key != "bin_name"
                    }
            elif isinstance(build_options_cfg, (str, list)):
                flags_cfg = build_options_cfg

            return guest_name, get_platform_build_flags(flags_cfg, platform_name)

        guest_classes = {
            "baremetal": baremetal_test,
        }
        if BAREMETAL_BENCHMARK is not None:
            guest_classes["baremetal_benchmark"] = BAREMETAL_BENCHMARK

        vm_entries = self.test_config.get("vms", [])
        if not isinstance(vm_entries, list):
            vm_entries = []

        for vm_idx, vm_entry in enumerate(vm_entries, start=1):
            if not isinstance(vm_entry, dict):
                continue
            vm_data = next(iter(vm_entry.values()), {})
            if not isinstance(vm_data, dict):
                continue

            guest_type = str(vm_data.get("name", "")).lower()
            if not guest_type:
                raise ValueError(
                    f"Missing guest name in VM entry #{vm_idx} "
                    f"for setup '{self.test_config.get('setup', '')}'."
                )
            print_log("INFO", f"Building guest {guest_type}:", tab_level=1)

            guest_name, building_flags = resolve_guest_build_options(
                vm_data.get("build_options", {}),
                guest_type,
                self.test_config["platform"],
            )
            if building_flags.get("cpu_num") in (None, ""):
                platform_cfg = vm_data.get("platform_cfg", {})
                if isinstance(platform_cfg, dict):
                    platform_cpu_num = platform_cfg.get("cpu_num")
                    if platform_cpu_num not in (None, ""):
                        building_flags["cpu_num"] = platform_cpu_num

            print_log("INFO", f"Building guest_type: {guest_type}", tab_level=2)
            print_log("INFO", f"Building bin_name: {guest_name}", tab_level=2)
            print_log("INFO", f"Building flags: {building_flags}", tab_level=2)

            guest_class = guest_classes.get(guest_type)
            if guest_class is None:
                raise ValueError(f"Unsupported guest type '{guest_type}'")

            list_tests = self.test_config["tests"]
            list_suites = self.test_config["suites"]
            benchmark = self.test_config["benchmark"]

            guest_instance = guest_class(
                self.wrkdir,
                list_tests,
                list_suites,
                benchmark,
                bkao_dir=BKAO_DIR,
                tests_srcs=TESTS_DIR,
                bin_name=guest_name,
                build_flags=building_flags,
            )

            self.list_obj.append(guest_instance)

            guest_instance.build(
                platform=self.test_config["platform"],
                arch=platform.architecture,
                toolchain=platform.toolchain,
                irq_flags=irq_flags or {},
            )

    @staticmethod
    def run_cmd(cmd, cwd=None):
        proc_result = subprocess.run(cmd, cwd=cwd, text=True, check=False)

        if proc_result.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def build_run_bin(self, wrkdir, config_path, platform):
        wrkdir_abs = os.path.abspath(wrkdir)

        guests_build_dir = os.path.join(wrkdir_abs, "guests", "build")
        platform_name = self.test_config["platform"]

        env = os.environ.copy()
        env["ARCH"] = platform.architecture
        env["CROSS_COMPILE"] = f"{platform.toolchain}"

        hypervisor_dict = {
            "bao": bao,
            "none": standalone,
            "standalone": standalone,
        }

        hypervisor_class = hypervisor_dict.get(self.hypervisor)
        if hypervisor_class is None:
            raise ValueError(f"Unsupported hypervisor mode '{self.hypervisor}'.")
        hypervisor_instance = hypervisor_class(wrkdir)

        hypervisor_instance.fetch_sources(self.hypervisor_srcs)
        hypervisor_instance.clean(hypervisor_instance.srcs_path)

        out_bin_path, bin_name, elf_name = hypervisor_instance.build(
            wrkdir_imgs=guests_build_dir,
            config_repo=config_path,
            config_name=platform_name,
            platform=platform_name,
            env=env,
        )

        print_log("SUCCESS", "Successfully built final image!", tab_level=1)
        return out_bin_path, bin_name, elf_name

    def clean_build_artifacts(self):
        """Placeholder for future targeted artifact cleanup."""
        self.cleanup()

    def populate_tests(self):
        src_dir = os.path.join(TESTS_DIR, "src")
        self.tests = []

        c_files = sorted(f for f in os.listdir(src_dir) if f.endswith(".c"))
        for suite_nr, fname in enumerate(c_files, start=1):
            with open(os.path.join(src_dir, fname), encoding="utf-8") as source_file:
                content = source_file.read()

            for test_nr, match in enumerate(
                re.finditer(r'BAO_TEST\s*\(([^)]+)\)', content)
            ):
                args = [a.strip().strip('"') for a in match.group(1).split(",")]
                self.tests.append({
                    "id": suite_nr * 100 + test_nr,
                    "suite_nr": suite_nr,
                    "test_nr": test_nr,
                    "suite": args[0] if len(args) > 0 else "",
                    "name": args[1] if len(args) > 1 else "",
                    "setup": args[2] if len(args) > 2 else "",
                    "guests": args[2].split("+") if len(args) > 2 else [],
                    "description": args[3] if len(args) > 3 else "",
                    "file": fname,
                })

        return self.tests

    def populate_plats(self):
        self.plats = []

        skip = {"generic_platform.py"}

        print_log("INFO", "Loading platform libs...", tab_level=1)
        for fname in os.listdir(BKAO_PLAT_DIR):
            if not fname.endswith(".py") or fname in skip:
                continue
            stem = fname[:-3]
            class_n = stem.replace("-", "_")
            fpath = os.path.join(BKAO_PLAT_DIR, fname)

            spec = importlib.util.spec_from_file_location(class_n, fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            self.plats.append((stem, getattr(mod, class_n)))

        fpath = os.path.join(BKAO_PLAT_DIR, "generic_platform.py")
        spec = importlib.util.spec_from_file_location("generic_platform", fpath)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    def populate_benchmarks(self):
        self.benchmarks = []
        benchmark_src_root = os.path.join(BENCHS_DIR, "src", "benchmarks")
        benchmark_cfg_root = os.path.join(BENCHS_DIR, "configs")
        if not os.path.isdir(benchmark_src_root) or not os.path.isdir(benchmark_cfg_root):
            return self.benchmarks

        def name_candidates(name):
            raw_name = str(name).strip().lower()
            candidates = [
                raw_name,
                raw_name.replace("_", "-"),
                raw_name.replace("-", "_"),
            ]
            return [
                candidate
                for i, candidate in enumerate(candidates)
                if candidate and candidate not in candidates[:i]
            ]

        def resolve_existing_subdir(base_dir, name):
            for candidate in name_candidates(name):
                if os.path.isdir(os.path.join(base_dir, candidate)):
                    return candidate
            return None

        def has_any_yaml(config_dir):
            for _root, _, files in os.walk(config_dir):
                for file_name in files:
                    if file_name.endswith((".yaml", ".yml")):
                        return True
            return False

        def extract_benchmark_description(source_dir):
            pattern = re.compile(r"BAO_BENCHMARK_DESC\s*:\s*(.+)")
            for root, _, files in os.walk(source_dir):
                for file_name in sorted(files):
                    if not file_name.endswith(".c"):
                        continue

                    source_path = os.path.join(root, file_name)
                    try:
                        with open(source_path, "r", encoding="utf8") as source_file:
                            for line in source_file:
                                match = pattern.search(line)
                                if match:
                                    description = (
                                        match.group(1).strip().rstrip("*/").strip()
                                    )
                                    if description:
                                        return description
                    except OSError as exc:
                        print_log(
                            "WARNING",
                            "Could not read benchmark source "
                            f"'{source_path}' for description: {exc}.",
                            tab_level=1,
                        )
            return None

        benchmark_dirs = sorted(
            entry for entry in os.listdir(benchmark_src_root)
            if os.path.isdir(os.path.join(benchmark_src_root, entry))
        )

        for benchmark_name in benchmark_dirs:
            benchmark_src_dir = os.path.join(benchmark_src_root, benchmark_name)
            guest_dirs = sorted(
                entry for entry in os.listdir(benchmark_src_dir)
                if os.path.isdir(os.path.join(benchmark_src_dir, entry))
            )
            if not guest_dirs:
                print_log(
                    "WARNING",
                    "Skipping benchmark "
                    f"'{benchmark_name}': no guest directories found in "
                    f"'{benchmark_src_dir}'.",
                    tab_level=1,
                )
                continue

            setup_name = resolve_existing_subdir(benchmark_cfg_root, benchmark_name)
            if setup_name is None:
                print_log(
                    "WARNING",
                    f"Skipping benchmark '{benchmark_name}': config directory "
                    f"not found under '{benchmark_cfg_root}'.",
                    tab_level=1,
                )
                continue

            setup_cfg_dir = os.path.join(benchmark_cfg_root, setup_name)
            if not has_any_yaml(setup_cfg_dir):
                print_log(
                    "WARNING",
                    f"Skipping benchmark '{benchmark_name}': no YAML configs "
                    f"found under '{setup_cfg_dir}'.",
                    tab_level=1,
                )
                continue

            bench_nr = len(self.benchmarks)
            benchmark_description = extract_benchmark_description(benchmark_src_dir)

            self.benchmarks.append(
                {
                    "id": 100 + bench_nr,
                    "suite_nr": 1,
                    "test_nr": bench_nr,
                    "suite": "BENCHMARK",
                    "name": benchmark_name,
                    "setup": setup_name,
                    "guests": ["baremetal_benchmark"],
                    "description": (
                        benchmark_description
                        or f"Benchmark '{benchmark_name}'"
                    ),
                    "file": benchmark_name,
                    "benchmark": benchmark_name,
                }
            )
        return self.benchmarks
    def populate_guests(self, workloads=None):
        self.guests = []
        workloads = workloads if workloads is not None else self.tests
        for workload in workloads:
            for guest in workload.get("guests", []):
                guest_lower = str(guest).lower()
                if guest_lower not in self.guests:
                    self.guests.append(guest_lower)

        return self.guests

    @staticmethod
    def validate_workload_ids(workload_ids, workloads, workload_type):
        valid_ids = {workload["id"] for workload in workloads}
        for workload_id in workload_ids:
            if workload_id not in valid_ids:
                raise ValueError(
                    f"Invalid {workload_type} ID: {workload_id}. "
                    f"Valid IDs are: {sorted(valid_ids)}"
                )

    def validate_tests(self, test_ids):
        self.validate_workload_ids(test_ids, self.tests, "test")

    def parse_args(self):
        args = CLI().bkao_config(platforms=[plat[0] for plat in self.plats])

        benchmark_mode_requested = (
            args.benchmark is not None or bool(args.benchmark_exclude)
        )
        if benchmark_mode_requested:
            self.run_type = "benchmark"
            workloads = self.benchmarks
            include_ids = args.benchmark
            exclude_ids = args.benchmark_exclude
        else:
            self.run_type = "test"
            workloads = self.tests
            include_ids = args.test
            exclude_ids = args.test_exclude

        all_ids = [workload["id"] for workload in workloads]
        workloads_to_run = []

        def parse_id_list(id_list, label):
            parsed_ids = []
            invalid_ids = []

            for raw_id in id_list:
                id_value = str(raw_id).strip()
                try:
                    parsed_ids.append(int(id_value))
                except ValueError:
                    invalid_ids.append(id_value if id_value else "<empty>")

            if invalid_ids:
                raise ValueError(
                    f"{label} IDs must be integers. Invalid values: "
                    f"{', '.join(invalid_ids)}."
                )

            return parsed_ids

        if include_ids is None or include_ids == "all":
            workloads_to_run = all_ids
        else:
            workloads_to_run = parse_id_list(
                include_ids,
                self.run_type.capitalize(),
            )

        if exclude_ids:
            excluded = set(
                parse_id_list(exclude_ids, f"Excluded {self.run_type}")
            )
            workloads_to_run = [
                workload_id
                for workload_id in workloads_to_run
                if workload_id not in excluded
            ]

        workload_label = self.run_type.capitalize()
        print_log("INFO", f"Validating {self.run_type} IDs...", tab_level=0)
        self.validate_workload_ids(workloads_to_run, workloads, self.run_type)
        print_log(
            "SUCCESS",
            f"{workload_label}s to run: {', '.join(map(str, workloads_to_run))}.",
            tab_level=0,
        )

        self.tests_to_run = [
            workload for workload in workloads
            if workload["id"] in workloads_to_run
        ]

        self.runtime_config = {
            "log_level": int(args.log_level),
            "echo": args.echo,
            "platform": args.platform,
            "platform_args": args.plat_virt_args,
            "firmware_build": not args.no_firmware_build,
            "toolchain_build": not args.no_toolchain_build,
            "hypervisor": args.hypervisor,
            "hypervisor_srcs": args.hyp_srcs,
        }

        if args.generate_id_readme is not None:
            self.generate_id_readme()

    def launch_test(
        self,
        run_bin,
        irq_flags,
        setup,
        echo,
        platform,
        benchmark_name=None,
    ):
        logger_inst = logger.TestLogger(
            platform.cpu_freq,
            platform.timer_freq,
            benchmark_name=benchmark_name if self.run_type == "benchmark" else None,
        )

        guests_bins = os.path.join(self.wrkdir, "guests", "build")

        if platform.is_emulated:
            try:
                proc, _stderr_path, _errf, serial_ports = platform.launch_test(
                    run_bin, irq_flags, guests_bins, setup, self.hypervisor
                )

                if proc.poll() is not None:
                    raise RuntimeError("QEMU died before serial connection")
                log_threads = logger_inst.connect_to_platform_port(
                    serial_ports,
                    echo,
                    self.run_type == "benchmark",
                )

                logger_inst.wait_for_finish(log_threads)

                if proc is not None:
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except (OSError, ProcessLookupError):
                        proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        try:
                            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        except (OSError, ProcessLookupError):
                            proc.kill()
                        proc.wait(timeout=5)
            finally:
                platform_cleanup = getattr(platform, "cleanup", None)
                if callable(platform_cleanup):
                    platform_cleanup()

        else:
            serial_ports = platform.get_serial_ports()
            log_threads = logger_inst.connect_to_platform_port(
                serial_ports,
                echo,
                self.run_type == "benchmark",
            )
            proc = platform.launch_test(
                run_bin, irq_flags, guests_bins, setup, self.hypervisor
            )

            logger_inst.wait_for_finish(log_threads)

            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

            if proc.returncode != 0:
                err = proc.stderr.read() if proc.stderr else ""
                raise RuntimeError(f"Command failed: {err}")

        if not serial_ports:
            print("[INFO] No serial ports returned by platform. Skipping logger and cleanup.")
            return

    def cleanup(self):
        guest_build_path = os.path.join(self.wrkdir, "guests")
        if os.path.exists(guest_build_path):
            print_log(
                "INFO",
                f"Removing guest build artifacts at: {guest_build_path}",
                tab_level=1,
            )
            shutil.rmtree(guest_build_path)
        hypervisor_path = os.path.join(self.wrkdir, "hypervisor")
        if os.path.exists(hypervisor_path):
            print_log(
                "INFO",
                f"Removing hypervisor sources at: {hypervisor_path}",
                tab_level=1,
            )
            shutil.rmtree(hypervisor_path)

    def generate_id_readme(self):
        pretty_table_cls = getattr(
            importlib.import_module("prettytable"),
            "PrettyTable",
        )
        table_tests = pretty_table_cls()
        table_tests.field_names = [
            "ID",
            "Suite",
            "Name",
            "Setup",
            "Description",
            "File",
        ]
        for test in self.tests:
            table_tests.add_row(
                [
                    test["id"],
                    test["suite"],
                    test["name"],
                    test["setup"],
                    test["description"],
                    test["file"],
                ]
            )
        print(table_tests)

        table_benchs = pretty_table_cls()
        table_benchs.field_names = ["ID", "Name", "Setup", "Description", "File"]
        for bench in self.benchmarks:
            table_benchs.add_row(
                [
                    bench["id"],
                    bench["name"],
                    bench["setup"],
                    bench["description"],
                    bench["file"],
                ]
            )
        print(table_benchs)

        sys.exit(0)

test_framework = TestFramework  # pylint: disable=invalid-name

def launch_tests(bkao_runner, tests, platform, wrkdir):
    group_key = "benchmark" if bkao_runner.run_type == "benchmark" else "setup"
    setup_groups = {}
    for test in tests:
        setup = test.get(group_key) or test.get("setup")
        if setup not in setup_groups:
            setup_groups[setup] = []
        setup_groups[setup].append(test)

    raw_irq_flags = getattr(platform, "irq_flags", {})
    if (
        isinstance(raw_irq_flags, tuple)
        and len(raw_irq_flags) == 1
        and isinstance(raw_irq_flags[0], dict)
    ):
        raw_irq_flags = raw_irq_flags[0]
    base_interrupt_flags = (
        dict(raw_irq_flags) if isinstance(raw_irq_flags, dict) else {}
    )

    for setup, grouped_tests in setup_groups.items():
        interrupt_flags = dict(base_interrupt_flags)
        test_ids = [test["id"] for test in grouped_tests]
        is_benchmark = bkao_runner.run_type == "benchmark"
        platform_name = _get_platform_name(platform)

        if is_benchmark:
            benchmark_name = str(grouped_tests[0].get("benchmark", setup)).strip()
            setup_name = str(grouped_tests[0].get("setup", benchmark_name)).lower()
            setup_cfg_path = os.path.join(BENCHS_DIR, "configs", setup_name)
            if not os.path.isdir(setup_cfg_path):
                raise FileNotFoundError(
                    f"Could not find benchmark config directory '{setup_cfg_path}'."
                )

            vm_configs = read_config(setup_cfg_path, platform)
            generated_cfg_dir = os.path.join(
                wrkdir,
                "configs",
                "benchmarks",
                setup_name,
            )

            platform_cfg_dir = os.path.join(setup_cfg_path, platform_name)
            if os.path.isdir(platform_cfg_dir):
                generated_platform_cfg_dir = os.path.join(
                    generated_cfg_dir,
                    platform_name,
                )
                os.makedirs(generated_platform_cfg_dir, exist_ok=True)
                for item in os.listdir(platform_cfg_dir):
                    src_path = os.path.join(platform_cfg_dir, item)
                    dst_path = os.path.join(generated_platform_cfg_dir, item)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dst_path)

            generated_cfg_file = write_config(
                setup_cfg_path,
                platform,
                output_dir=generated_cfg_dir,
            )
            bao_cfg_repo_abs = os.path.abspath(generated_cfg_dir)
            bao_cfg_file_abs = os.path.abspath(generated_cfg_file)
            interrupt_flags["bao_config_path"] = bao_cfg_file_abs
            print_log(
                "INFO",
                f"Preparing Benchmark IDs {test_ids}: {benchmark_name}.",
                tab_level=0,
            )
        else:
            setup_name = str(setup).lower()
            setup_cfg_path = os.path.join(TESTS_DIR, "configs", setup_name)
            vm_configs = read_config(setup_cfg_path, platform)
            generated_cfg_dir = os.path.join(
                wrkdir,
                "configs",
                "tests",
                setup_name,
            )

            platform_cfg_dir = os.path.join(setup_cfg_path, platform_name)
            if os.path.isdir(platform_cfg_dir):
                generated_platform_cfg_dir = os.path.join(
                    generated_cfg_dir,
                    platform_name,
                )
                os.makedirs(generated_platform_cfg_dir, exist_ok=True)
                for item in os.listdir(platform_cfg_dir):
                    src_path = os.path.join(platform_cfg_dir, item)
                    dst_path = os.path.join(generated_platform_cfg_dir, item)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src_path, dst_path)

            generated_cfg_file = write_config(
                setup_cfg_path,
                platform,
                output_dir=generated_cfg_dir,
            )
            bao_cfg_repo_abs = os.path.abspath(generated_cfg_dir)
            bao_cfg_file_abs = os.path.abspath(generated_cfg_file)
            interrupt_flags["bao_config_path"] = bao_cfg_file_abs
            print_log(
                "INFO",
                f"Preparing Test IDs {test_ids}: "
                f"{grouped_tests[0]['suite']} - {grouped_tests[0]['name']} "
                f"(and others with same setup)...",
                tab_level=0,
            )

        bkao_runner.hypervisor = bkao_runner.runtime_config.get("hypervisor", "bao")
        bkao_runner.hypervisor_srcs = bkao_runner.runtime_config.get(
            "hypervisor_srcs",
            "",
        )
        bkao_runner.test_config = {
            "platform": platform_name,
            "setup": setup_name,
            "echo": bkao_runner.runtime_config.get("echo", "tf"),
            "tests": " ".join(
                dict.fromkeys(
                    test["name"]
                    for test in grouped_tests
                    if test.get("name")
                )
            ),
            "suites": " ".join(
                dict.fromkeys(
                    test["suite"]
                    for test in grouped_tests
                    if test.get("suite")
                )
            ),
            "benchmark": benchmark_name if is_benchmark else False,
            "vms": vm_configs,
        }

        if "GIC_version" not in interrupt_flags:
            platform_args = bkao_runner.runtime_config.get("platform_args", "")
            if isinstance(platform_args, str):
                platform_args = [
                    arg.strip()
                    for arg in platform_args.split(",")
                    if arg.strip()
                ]
            else:
                platform_args = []
            for arg in platform_args:
                if arg.upper().startswith("GICV"):
                    interrupt_flags["GIC_version"] = arg.upper()
                    break

        workload_prefix = "B" if is_benchmark else "T"
        print_log(
            "INFO",
            f"{workload_prefix}{test_ids}: Building guests ...",
            tab_level=0,
        )
        bkao_runner.build_guests(platform, interrupt_flags)

        print_log(
            "INFO",
            f"Building run image [{bkao_runner.hypervisor}]...",
            tab_level=0,
        )
        run_bin, _bin_name, _elf_name = bkao_runner.build_run_bin(
            wrkdir,
            bao_cfg_repo_abs,
            platform,
        )

        if bkao_runner.runtime_config.get("firmware_build", True):
            platform.build_firmware(run_bin, interrupt_flags)

        bkao_runner.launch_test(
            run_bin,
            interrupt_flags,
            setup_name,
            bkao_runner.runtime_config.get("echo", "tf"),
            platform,
            benchmark_name=benchmark_name if is_benchmark else None,
        )

def main():
    print_log("INFO", "Starting Bao Kao Framework...", tab_level=0)
    print_log("INFO", f"Current working directory: {CUR_DIR}", tab_level=1)
    wrkdir = os.path.join(CUR_DIR, "wrkdir")
    os.makedirs(wrkdir, exist_ok=True)

    bkao_runner = TestFramework(wrkdir)

    print_log("INFO", "Populating tests ...", tab_level=0)
    bkao_runner.populate_tests()
    print_log("SUCCESS", "Tests populated.", tab_level=0)

    print_log("INFO", "Populating benchmarks ...", tab_level=0)
    benchmarks = bkao_runner.populate_benchmarks()
    if benchmarks:
        print_log("SUCCESS", "Benchmarks populated.", tab_level=0)
    else:
        print_log("WARNING", "No runnable benchmarks discovered.", tab_level=0)

    print_log("INFO", "Populating platforms ...", tab_level=0)
    bkao_runner.populate_plats()
    print_log(
        "SUCCESS",
        f"Platforms populated: {', '.join([plat[0] for plat in bkao_runner.plats])}.",
        tab_level=0,
    )

    print_log("INFO", "Reading TF configuration ...", tab_level=0)
    bkao_runner.parse_args()
    print_log("SUCCESS", "Runtime TF configuration built.", tab_level=0)

    print_log("INFO", "Populating guests to build ...", tab_level=0)
    guests = bkao_runner.populate_guests(bkao_runner.tests_to_run)
    print_log("SUCCESS", f"Guests populated: {', '.join(guests)}.", tab_level=0)

    print_log("INFO", "Cleaning up build artifacts from previous runs...", tab_level=0)
    bkao_runner.cleanup()

    print_log("INFO", "Setting up platform...", tab_level=0)
    requested_platform = bkao_runner.runtime_config["platform"]
    platform_class = _resolve_platform_class(bkao_runner.plats, requested_platform)
    if platform_class is None:
        available_platforms = sorted(
            {name.replace("_", "-") for name, _ in bkao_runner.plats}
        )
        raise ValueError(
            f"Unsupported platform '{requested_platform}'. "
            f"Available platforms: {', '.join(available_platforms)}."
        )
    plat = platform_class(wrkdir)
    plat.setup_platform()

    if bkao_runner.runtime_config["toolchain_build"]:
        plat.build_toolchain()
    else:
        plat.toolchain = plat.toolchain_prefix
        print_log(
            "INFO",
            "Skipping toolchain build, expecting "
            f"'{plat.toolchain_prefix}' to be available in the environment.",
            tab_level=1,
        )

    test_ids = [test["id"] for test in bkao_runner.tests_to_run]
    print_log(
        "INFO",
        f"Preparing to launch {bkao_runner.run_type} IDs {test_ids} "
        f"on platform {bkao_runner.runtime_config['platform']}...",
        tab_level=0,
    )
    launch_tests(bkao_runner, bkao_runner.tests_to_run, plat, wrkdir)

    bkao_runner.cleanup()

if __name__ == "__main__":
    main()
