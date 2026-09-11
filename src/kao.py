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

KAO_DIR = os.path.dirname(os.path.abspath(__file__))  # tests/tf/src/
KAO_FW_DIR = os.path.join(KAO_DIR, "firmware")  # tests/tf/src/firmware
KAO_GUEST_DIR = os.path.join(KAO_DIR, "guests")  # tests/tf/src/guests/
KAO_HYP_DIR = os.path.join(KAO_DIR, "hypervisor")  # tests/tf/src/hypervisor
KAO_PLAT_DIR = os.path.join(KAO_DIR, "platforms")  # tests/tf/src/platforms/
KAO_TOOL_DIR = os.path.join(KAO_DIR, "toolchains")  # tests/tf/src/toolchains/
KAO_UTILS_DIR = os.path.join(KAO_DIR, "utils")  # tests/tf/src/utils/

KAO_ROOT = os.path.abspath(os.path.join(KAO_DIR, "../"))  # tests/tf/
TESTS_DIR = os.path.abspath(os.path.join(KAO_ROOT, "../tests"))  # tests/tests
BENCHS_DIR = os.path.abspath(os.path.join(KAO_ROOT, "../benchs"))  # tests/benchs
HYPERVISOR_DIR = os.path.abspath(os.path.join(KAO_ROOT, "../../"))  # bao-hypervisor/

# Load each module/class to system path
sys.path.append(KAO_DIR)
sys.path.append(KAO_FW_DIR)
sys.path.append(KAO_GUEST_DIR)
sys.path.append(KAO_HYP_DIR)
sys.path.append(KAO_PLAT_DIR)
sys.path.append(KAO_TOOL_DIR)
sys.path.append(KAO_UTILS_DIR)

BAREMETAL_BENCHMARK = None
WRKDIR_MARKER = ".kao-wrkdir"
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
available_envs = getattr(config_renderer_module, "available_envs")
list_sources = getattr(importlib.import_module("utils.codegen"), "list_sources")
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

def prepare_wrkdir(wrkdir):
    """Create or validate a working directory owned by Bao Kao."""
    wrkdir = os.path.abspath(wrkdir)
    marker = os.path.join(wrkdir, WRKDIR_MARKER)

    if os.path.exists(wrkdir):
        if not os.path.isdir(wrkdir):
            raise RuntimeError(f"Working directory is not a directory: {wrkdir}")
        if not os.path.isfile(marker):
            raise RuntimeError(
                f"Refusing to use unmarked working directory: {wrkdir}"
            )
    else:
        os.makedirs(wrkdir)
        with open(marker, "x", encoding="utf-8"):
            pass

    return wrkdir

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
        self.cli_args = None
        self.tests_root = TESTS_DIR
        self.tests_sources = None
        self.envs_dir = os.path.join(TESTS_DIR, "envs")

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
                    f"for environment '{self.test_config.get('env', '')}'."
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

            guest_instance = guest_class(
                self.wrkdir,
                self.test_config["tests"],
                self.test_config["benchmark"],
                kao_dir=KAO_DIR,
                tests_srcs=os.path.join(self.tests_root, "src"),
                bin_name=guest_name,
                build_flags=building_flags,
            )

            self.list_obj.append(guest_instance)

            guest_instance.build(
                platform=self.test_config["platform"],
                arch=platform.architecture,
                toolchain=platform.toolchain,
                irq_flags=irq_flags or {},
                log_level=self.runtime_config.get("log_level", 0),
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

        out_bin_path, bin_name, elf_name = hypervisor_instance.build(
            wrkdir_imgs=guests_build_dir,
            config_repo=config_path,
            config_name=platform_name,
            platform=platform_name,
            env=env,
        )

        print_log("SUCCESS", "Successfully built final image!", tab_level=1)
        return out_bin_path, bin_name, elf_name

    def discover_tests(self, platform):
        """Discover the tests in the candidate sources through the guest build."""
        files = list_sources(os.path.join(self.tests_root, "src"), self.tests_sources)
        guest = baremetal_test(
            self.wrkdir,
            None,
            False,
            kao_dir=KAO_DIR,
            tests_srcs=os.path.join(self.tests_root, "src"),
            bin_name="baremetal",
            build_flags={},
        )
        guest.prepare(
            platform=_get_platform_name(platform),
            arch=platform.architecture,
            toolchain=platform.toolchain,
            irq_flags=base_interrupt_flags(self, platform),
            log_level=self.runtime_config.get("log_level", 0),
        )
        self.tests = guest.discover(files)
        return self.tests

    def populate_plats(self):
        self.plats = []

        skip = {"generic_platform.py"}

        print_log("INFO", "Loading platform libs...", tab_level=1)
        for fname in os.listdir(KAO_PLAT_DIR):
            if not fname.endswith(".py") or fname in skip:
                continue
            stem = fname[:-3]
            class_n = stem.replace("-", "_")
            fpath = os.path.join(KAO_PLAT_DIR, fname)

            spec = importlib.util.spec_from_file_location(class_n, fpath)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            self.plats.append((stem, getattr(mod, class_n)))

        fpath = os.path.join(KAO_PLAT_DIR, "generic_platform.py")
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
            pattern = re.compile(r"KAO_BENCHMARK_DESC\s*:\s*(.+)")
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

    @staticmethod
    def validate_workload_ids(workload_ids, workloads, workload_type):
        valid_ids = {workload["id"] for workload in workloads}
        for workload_id in workload_ids:
            if workload_id not in valid_ids:
                raise ValueError(
                    f"Invalid {workload_type} ID: {workload_id}. "
                    f"Valid IDs are: {sorted(valid_ids)}"
                )

    @staticmethod
    def parse_id_list(id_list, label, numeric):
        parsed_ids = []
        invalid_ids = []

        for raw_id in id_list:
            id_value = str(raw_id).strip()
            try:
                parsed_ids.append(int(id_value) if numeric else id_value)
            except ValueError:
                invalid_ids.append(id_value if id_value else "<empty>")

        if invalid_ids:
            raise ValueError(
                f"{label} IDs must be integers. Invalid values: "
                f"{', '.join(invalid_ids)}."
            )

        return parsed_ids

    def _select_ids(self, workloads, include_ids, exclude_ids):
        numeric = self.run_type == "benchmark"
        if include_ids is None or include_ids == "all":
            selected = [workload["id"] for workload in workloads]
        else:
            selected = self.parse_id_list(include_ids, self.run_type.capitalize(), numeric)

        if exclude_ids:
            label = f"Excluded {self.run_type}"
            excluded = set(self.parse_id_list(exclude_ids, label, numeric))
            selected = [wid for wid in selected if wid not in excluded]

        print_log("INFO", f"Validating {self.run_type} IDs...", tab_level=0)
        self.validate_workload_ids(selected, workloads, self.run_type)
        return [workload for workload in workloads if workload["id"] in selected]

    def select_benchmarks(self):
        args = self.cli_args
        self.tests_to_run = self._select_ids(
            self.benchmarks, args.benchmark, args.benchmark_exclude
        )
        ids = ", ".join(str(bench["id"]) for bench in self.tests_to_run)
        print_log("SUCCESS", f"Benchmarks to run: {ids}.", tab_level=0)
        return self.tests_to_run

    def select_tests(self, platform):
        """Apply id, tag and environment filters; one run unit per (test, env)."""
        args = self.cli_args
        selected = self._select_ids(self.tests, args.test, args.test_exclude)

        if args.tags is not None:
            wanted = set(args.tags)
            selected = [test for test in selected if wanted <= set(test["tags"])]
        if args.exclude_tags is not None:
            unwanted = set(args.exclude_tags)
            selected = [test for test in selected if not unwanted & set(test["tags"])]

        platform_name = _get_platform_name(platform)
        available = available_envs(self.envs_dir, platform_name)
        if args.env is not None:
            unknown = [env for env in args.env if env not in available]
            if unknown:
                raise ValueError(
                    f"Environment(s) {', '.join(unknown)} not available for platform "
                    f"'{platform_name}'. Available: {', '.join(available) or 'none'}."
                )
            available = [env for env in available if env in args.env]

        self.tests_to_run = []
        skipped = []
        for test in selected:
            envs = [env for env in test["envs"] if env in available]
            if not envs:
                skipped.append(test)
                continue
            for env in envs:
                self.tests_to_run.append({**test, "env": env})
        self.tests_to_run.sort(key=lambda test: test["env"])

        for test in skipped:
            print_log(
                "WARNING",
                f"Skipping test {test['id']} ({test['name']}): none of its "
                f"environments ({', '.join(test['envs'])}) is available for "
                f"'{platform_name}'.",
                tab_level=0,
            )

        if not self.tests_to_run:
            raise ValueError(
                f"No tests selected for platform '{platform_name}'. "
                f"Available environments: {', '.join(available) or 'none'}."
            )

        for env in dict.fromkeys(test["env"] for test in self.tests_to_run):
            ids = ", ".join(t["id"] for t in self.tests_to_run if t["env"] == env)
            print_log("SUCCESS", f"Tests to run in '{env}': {ids}.", tab_level=0)

        return self.tests_to_run

    def parse_args(self):
        args = CLI().kao_config(platforms=[plat[0] for plat in self.plats])
        self.cli_args = args

        benchmark_mode_requested = (
            args.benchmark is not None or bool(args.benchmark_exclude)
        )
        self.run_type = "benchmark" if benchmark_mode_requested else "test"

        if args.tests_root:
            self.tests_root = os.path.abspath(args.tests_root)
        self.tests_sources = args.tests_src
        self.envs_dir = os.path.abspath(args.envs or os.path.join(self.tests_root, "envs"))

        self.runtime_config = {
            "log_level": int(args.log_level),
            "echo": args.echo,
            "platform": args.platform,
            "platform_args": args.plat_virt_args,
            "serial_ports": args.serial_port,
            "firmware_build": not args.no_firmware_build,
            "toolchain_build": not args.no_toolchain_build,
            "hypervisor": args.hypervisor,
            "hypervisor_srcs": args.hyp_srcs,
        }

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
            proc = None
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

                logger_inst.wait_for_finish(
                    log_threads,
                    timeout=platform.boot_timeout,
                )
            finally:
                if proc is not None and proc.poll() is None:
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

                platform_cleanup = getattr(platform, "cleanup", None)
                if callable(platform_cleanup):
                    platform_cleanup()

        else:
            serial_ports = self.runtime_config.get("serial_ports") or platform.get_serial_ports()
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
        marker = os.path.join(self.wrkdir, WRKDIR_MARKER)
        if not os.path.isfile(marker):
            raise RuntimeError(
                f"Refusing to clean unmarked working directory: {self.wrkdir}"
            )

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
            "Name",
            "Tags",
            "Envs",
            "Description",
            "File",
        ]
        for test in self.tests:
            table_tests.add_row(
                [
                    test["id"],
                    test["name"],
                    ", ".join(test["tags"]),
                    ", ".join(test["envs"]),
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

def base_interrupt_flags(kao_runner, platform):
    """Interrupt controller flags for the guest build: platform defaults plus CLI."""
    raw_irq_flags = getattr(platform, "irq_flags", {})
    if (
        isinstance(raw_irq_flags, tuple)
        and len(raw_irq_flags) == 1
        and isinstance(raw_irq_flags[0], dict)
    ):
        raw_irq_flags = raw_irq_flags[0]
    interrupt_flags = dict(raw_irq_flags) if isinstance(raw_irq_flags, dict) else {}

    platform_args = kao_runner.runtime_config.get("platform_args", "")
    if "GIC_version" not in interrupt_flags and isinstance(platform_args, str):
        for arg in platform_args.split(","):
            if arg.strip().upper().startswith("GICV"):
                interrupt_flags["GIC_version"] = arg.strip().upper()
                break
    return interrupt_flags

def launch_tests(kao_runner, tests, platform, wrkdir):
    group_key = "benchmark" if kao_runner.run_type == "benchmark" else "env"
    setup_groups = {}
    for test in tests:
        setup = test[group_key]
        if setup not in setup_groups:
            setup_groups[setup] = []
        setup_groups[setup].append(test)

    failed_groups = []
    for setup, grouped_tests in setup_groups.items():
        try:
            launch_group(kao_runner, platform, wrkdir, setup, grouped_tests)
        except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
            print_log("ERROR", f"Run for '{setup}' failed: {exc}", tab_level=0)
            failed_groups.append(setup)

    if failed_groups:
        raise RuntimeError(
            f"Runs failed for: {', '.join(failed_groups)} "
            f"({len(setup_groups) - len(failed_groups)} of {len(setup_groups)} completed)."
        )

def launch_group(kao_runner, platform, wrkdir, setup, grouped_tests):
    """Build, boot and run one environment (or benchmark) group."""
    interrupt_flags = base_interrupt_flags(kao_runner, platform)
    test_ids = [test["id"] for test in grouped_tests]
    is_benchmark = kao_runner.run_type == "benchmark"
    platform_name = _get_platform_name(platform)

    if is_benchmark:
        benchmark_name = str(grouped_tests[0].get("benchmark", setup)).strip()
        setup_name = str(grouped_tests[0].get("setup", benchmark_name)).lower()
        setup_cfg_path = os.path.join(BENCHS_DIR, "configs", setup_name)
        if not os.path.isdir(setup_cfg_path):
            raise FileNotFoundError(
                f"Could not find benchmark config directory '{setup_cfg_path}'."
            )
        generated_cfg_dir = os.path.join(wrkdir, "configs", "benchmarks", setup_name)
        print_log("INFO", f"Preparing Benchmark IDs {test_ids}: {benchmark_name}.", tab_level=0)
    else:
        benchmark_name = None
        setup_name = str(setup).lower()
        setup_cfg_path = os.path.join(kao_runner.envs_dir, setup_name)
        generated_cfg_dir = os.path.join(wrkdir, "envs", setup_name)
        print_log(
            "INFO",
            f"Preparing Test IDs {test_ids} in environment '{setup_name}'...",
            tab_level=0,
        )

    vm_configs = read_config(setup_cfg_path, platform)

    # Platform-specific extras next to the YAML (BSP sources, config.mk) travel
    # with the generated config so the hypervisor build finds them.
    platform_cfg_dir = os.path.join(setup_cfg_path, platform_name)
    if os.path.isdir(platform_cfg_dir):
        shutil.copytree(
            platform_cfg_dir,
            os.path.join(generated_cfg_dir, platform_name),
            dirs_exist_ok=True,
        )

    generated_cfg_file = write_config(setup_cfg_path, platform, output_dir=generated_cfg_dir)
    bao_cfg_repo_abs = os.path.abspath(generated_cfg_dir)
    interrupt_flags["bao_config_path"] = os.path.abspath(generated_cfg_file)

    kao_runner.hypervisor = kao_runner.runtime_config.get("hypervisor", "bao")
    kao_runner.hypervisor_srcs = kao_runner.runtime_config.get(
        "hypervisor_srcs",
        "",
    )
    kao_runner.test_config = {
        "platform": platform_name,
        "env": setup_name,
        "echo": kao_runner.runtime_config.get("echo", "tf"),
        "tests": grouped_tests,
        "benchmark": benchmark_name if is_benchmark else False,
        "vms": vm_configs,
    }

    workload_prefix = "B" if is_benchmark else "T"
    print_log(
        "INFO",
        f"{workload_prefix}{test_ids}: Building guests ...",
        tab_level=0,
    )
    kao_runner.build_guests(platform, interrupt_flags)

    print_log(
        "INFO",
        f"Building run image [{kao_runner.hypervisor}]...",
        tab_level=0,
    )
    run_bin, _bin_name, _elf_name = kao_runner.build_run_bin(
        wrkdir,
        bao_cfg_repo_abs,
        platform,
    )

    if kao_runner.runtime_config.get("firmware_build", True):
        platform.build_firmware(run_bin, interrupt_flags)

    kao_runner.launch_test(
        run_bin,
        interrupt_flags,
        setup_name,
        kao_runner.runtime_config.get("echo", "tf"),
        platform,
        benchmark_name=benchmark_name if is_benchmark else None,
    )

def main():
    print_log("INFO", "Starting Bao Kao Framework...", tab_level=0)
    print_log("INFO", f"Current working directory: {CUR_DIR}", tab_level=1)
    wrkdir = prepare_wrkdir(CLI.wrkdir())

    kao_runner = TestFramework(wrkdir)

    print_log("INFO", "Populating platforms ...", tab_level=0)
    kao_runner.populate_plats()
    print_log(
        "SUCCESS",
        f"Platforms populated: {', '.join([plat[0] for plat in kao_runner.plats])}.",
        tab_level=0,
    )

    print_log("INFO", "Reading TF configuration ...", tab_level=0)
    kao_runner.parse_args()
    print_log("SUCCESS", "Runtime TF configuration built.", tab_level=0)

    requested_platform = kao_runner.runtime_config["platform"]
    platform_class = _resolve_platform_class(kao_runner.plats, requested_platform)
    if platform_class is None:
        available_platforms = sorted(
            {name.replace("_", "-") for name, _ in kao_runner.plats}
        )
        raise ValueError(
            f"Unsupported platform '{requested_platform}'. "
            f"Available platforms: {', '.join(available_platforms)}."
        )
    plat = platform_class(wrkdir)

    print_log("INFO", "Cleaning up build artifacts from previous runs...", tab_level=0)
    kao_runner.cleanup()

    print_log("INFO", "Setting up platform...", tab_level=0)
    plat.setup_platform()

    if kao_runner.runtime_config["toolchain_build"]:
        plat.build_toolchain()
    else:
        plat.toolchain = plat.toolchain_prefix
        print_log(
            "INFO",
            "Skipping toolchain build, expecting "
            f"'{plat.toolchain_prefix}' to be available in the environment.",
            tab_level=1,
        )

    print_log("INFO", "Discovering tests ...", tab_level=0)
    kao_runner.discover_tests(plat)
    print_log("SUCCESS", f"Tests discovered: {len(kao_runner.tests)}.", tab_level=0)

    print_log("INFO", "Populating benchmarks ...", tab_level=0)
    if not kao_runner.populate_benchmarks():
        print_log("WARNING", "No runnable benchmarks discovered.", tab_level=0)

    if kao_runner.cli_args.generate_id_readme is not None:
        kao_runner.generate_id_readme()

    print_log("INFO", f"Selecting {kao_runner.run_type}s ...", tab_level=0)
    if kao_runner.run_type == "benchmark":
        kao_runner.select_benchmarks()
    else:
        kao_runner.select_tests(plat)

    test_ids = [test["id"] for test in kao_runner.tests_to_run]
    print_log(
        "INFO",
        f"Preparing to launch {kao_runner.run_type} IDs {test_ids} "
        f"on platform {kao_runner.runtime_config['platform']}...",
        tab_level=0,
    )
    launch_tests(kao_runner, kao_runner.tests_to_run, plat, wrkdir)

    kao_runner.cleanup()

if __name__ == "__main__":
    main()
