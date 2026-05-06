from asyncio import threads

from prettytable import PrettyTable
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

baremetal_benchmark = None
if os.path.exists(BENCHS_DIR) and os.listdir(BENCHS_DIR):
    sys.path.append(os.path.join(BENCHS_DIR, "guests"))
    from baremetal_benchmark import baremetal_benchmark

# Test Framework imports
from constants import print_log
from bao import bao
from generic import standalone
from baremetal  import baremetal_test


class test_framework:
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
                    flags_cfg = {key: value for key, value in build_options_cfg.items() if key != "bin_name"}
            elif isinstance(build_options_cfg, (str, list)):
                flags_cfg = build_options_cfg

            return guest_name, get_platform_build_flags(flags_cfg, platform_name)

        guest_classes = {
            "baremetal": baremetal_test,
        }
        if baremetal_benchmark is not None:
            guest_classes["baremetal_benchmark"] = baremetal_benchmark

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
                    f"Missing guest name in VM entry #{vm_idx} for setup '{self.test_config.get('setup', '')}'."
                )
            print_log("INFO", f"Building guest {guest_type}:", tab_level=1)

            guest_name, building_flags = resolve_guest_build_options(
                vm_data.get("build_options", {}),
                guest_type,
                self.test_config['platform'],
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
                self.wrkdir, list_tests, list_suites, benchmark,
                tf_dir = TF_DIR,
                tests_srcs=TESTS_DIR,
                bin_name = guest_name,
                build_flags = building_flags
            )

            self.list_obj.append(guest_instance)

            guest_instance.build(
                platform=self.test_config['platform'],
                arch=platform.architecture,
                toolchain=platform.toolchain,
                irq_flags=irq_flags or {}
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

    def populate_benchmarks(self):
        self.benchmarks = []
        benchmark_src_root = os.path.join(BENCHS_DIR, "src", "benchmarks")
        benchmark_cfg_root = os.path.join(BENCHS_DIR, "configs")
        if not os.path.isdir(benchmark_src_root) or not os.path.isdir(benchmark_cfg_root):
            return self.benchmarks

        def name_candidates(name):
            raw_name = str(name).strip().lower()
            candidates = [raw_name, raw_name.replace("_", "-"), raw_name.replace("-", "_")]
            return [candidate for i, candidate in enumerate(candidates) if candidate and candidate not in candidates[:i]]

        def resolve_existing_subdir(base_dir, name):
            for candidate in name_candidates(name):
                if os.path.isdir(os.path.join(base_dir, candidate)):
                    return candidate
            return None

        def has_any_yaml(config_dir):
            for root, _, files in os.walk(config_dir):
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
                                    description = match.group(1).strip().rstrip("*/").strip()
                                    if description:
                                        return description
                    except OSError as exc:
                        print_log(
                            "WARNING",
                            f"Could not read benchmark source '{source_path}' for description: {exc}.",
                            tab_level=1
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
                    f"Skipping benchmark '{benchmark_name}': no guest directories found in '{benchmark_src_dir}'.",
                    tab_level=1
                )
                continue

            setup_name = resolve_existing_subdir(benchmark_cfg_root, benchmark_name)
            if setup_name is None:
                print_log(
                    "WARNING",
                    f"Skipping benchmark '{benchmark_name}': config directory not found under '{benchmark_cfg_root}'.",
                    tab_level=1
                )
                continue

            setup_cfg_dir = os.path.join(benchmark_cfg_root, setup_name)
            if not has_any_yaml(setup_cfg_dir):
                print_log(
                    "WARNING",
                    f"Skipping benchmark '{benchmark_name}': no YAML configs found under '{setup_cfg_dir}'.",
                    tab_level=1
                )
                continue

            # Benchmark IDs follow discovery order from tests/benchs/src/benchmarks.
            # We only assign IDs to runnable benchmarks (matching config dir with YAML files).
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
                    "description": benchmark_description or f"Benchmark '{benchmark_name}'",
                    "file": benchmark_name,
                    "benchmark": benchmark_name,
                }
            )

        return self.benchmarks

    def populate_guests(self, workloads=None):
        self.guests = []
        workloads = workloads if workloads is not None else self.tests

        for workload in workloads:
            for guest in workload.get('guests', []):
                guest_lower = str(guest).lower()
                if guest_lower not in self.guests:
                    self.guests.append(guest_lower)

        return self.guests

    def validate_workload_ids(self, workload_ids, workloads, workload_type):
        valid_ids = {workload['id'] for workload in workloads}
        for workload_id in workload_ids:
            if workload_id not in valid_ids:
                raise ValueError(f"Invalid {workload_type} ID: {workload_id}. Valid IDs are: {sorted(valid_ids)}")

    def validate_tests(self, test_ids):
        self.validate_workload_ids(test_ids, self.tests, "test")

    def parse_args(self):
        args = CLI().tf_config(platforms=[plat[0] for plat in self.plats])

        benchmark_mode_requested = args.benchmark is not None or bool(args.benchmark_exclude)
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

        all_ids = [workload['id'] for workload in workloads]
        workloads_to_run = []

        if include_ids is not None and include_ids != "all":
            try:
                workloads_to_run = [int(workload_id) for workload_id in include_ids]
            except ValueError as exc:
                raise ValueError(f"{self.run_type.capitalize()} IDs must be integers.") from exc
        elif exclude_ids:
            try:
                excluded = {int(workload_id) for workload_id in exclude_ids}
            except ValueError as exc:
                raise ValueError(f"Excluded {self.run_type} IDs must be integers.") from exc
            workloads_to_run = [workload_id for workload_id in all_ids if workload_id not in excluded]
        else:
            workloads_to_run = all_ids

        workload_label = self.run_type.capitalize()
        print_log("INFO", f"Validating {self.run_type} IDs...", tab_level=0)
        self.validate_workload_ids(workloads_to_run, workloads, self.run_type)
        print_log("SUCCESS", f"{workload_label}s to run: {', '.join(map(str, workloads_to_run))}.", tab_level=0)

        # Keep the existing variable name for compatibility with the launch flow.
        self.tests_to_run = [workload for workload in workloads if workload['id'] in workloads_to_run]

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

        if args.generate_id_readme is not None:
            self.generate_id_readme()

    def launch_test(self, run_bin, irq_flags, setup, echo, platform, benchmark_name=None):
        logger_inst = logger.TestLogger(
            platform.cpu_freq,
            platform.timer_freq,
            benchmark_name=benchmark_name if self.run_type == "benchmark" else None
        )

        guests_bins = os.path.join(self.wrkdir, "guests", "build")

        if platform.is_emulated:
            try:
                proc, stderr_path, errf, serial_ports = platform.launch_test(
                    run_bin, irq_flags, guests_bins, setup, self.hypervisor
                )
                # time.sleep(1)

                if proc.poll() is not None:
                    raise RuntimeError("QEMU died before serial connection")
                log_threads = logger_inst.connect_to_platform_port(serial_ports, echo, self.run_type == "benchmark")

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
            log_threads = logger_inst.connect_to_platform_port(serial_ports, echo, self.run_type == "benchmark")
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

    def generate_id_readme(self):
        table_tests = PrettyTable()
        table_tests.field_names = ["ID", "Suite", "Name", "Setup", "Description", "File"]
        for test in self.tests:
            table_tests.add_row([test['id'], test['suite'], test['name'], test['setup'], test['description'], test['file']])
        print(table_tests)

        table_benchs = PrettyTable()
        table_benchs.field_names = ["ID", "Name", "Setup", "Description", "File"]
        for bench in self.benchmarks:
            table_benchs.add_row([bench['id'], bench['name'], bench['setup'], bench['description'], bench['file']])
        print(table_benchs)

        exit(0)


def _get_platform_name(platform):
    platform_name = getattr(platform, "platform_name", None)
    if platform_name:
        return platform_name
    return platform.__class__.__name__.replace("_", "-")


def _resolve_yaml_config_path(config_path, platform):
    platform_name = _get_platform_name(platform)
    candidates = [
        os.path.join(config_path, f"{platform_name}.yaml"),
        os.path.join(config_path, f"{platform_name}.yml"),
        os.path.join(config_path, platform_name, f"{platform_name}.yaml"),
        os.path.join(config_path, platform_name, f"{platform_name}.yml"),
    ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"Could not find YAML config for platform '{platform_name}' in '{config_path}'."
    )


def _extract_vm_entries(config_file):
    if not isinstance(config_file, dict):
        return []

    vm_entries = config_file.get("vms")
    if vm_entries is None:
        setup_cfg = config_file.get("setup", {})
        if isinstance(setup_cfg, dict):
            vm_entries = setup_cfg.get("vms", [])

    return vm_entries if isinstance(vm_entries, list) else []


def _normalize_vm_entry(vm_entry, vm_idx):
    vm_key = f"vm{vm_idx + 1}"

    if not isinstance(vm_entry, dict):
        return vm_key, {}

    vm_named_keys = [key for key in vm_entry if isinstance(key, str) and key.startswith("vm")]
    if vm_named_keys:
        vm_key = vm_named_keys[0]
        nested_cfg = vm_entry.get(vm_key)
        if isinstance(nested_cfg, dict):
            merged_cfg = dict(nested_cfg)
            for key, value in vm_entry.items():
                if key != vm_key:
                    merged_cfg.setdefault(key, value)
            return vm_key, merged_cfg

    return vm_key, vm_entry


def _to_c_literal(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return hex(value)
    return str(value)


def _write_field_block(lines, fields, indent):
    valid_fields = [(name, value) for name, value in fields if value is not None and value != ""]
    for field_idx, (name, value) in enumerate(valid_fields):
        suffix = "," if field_idx < (len(valid_fields) - 1) else ""
        lines.append(f"{indent}.{name} = {value}{suffix}")


def _flatten_c_designators(cfg, prefix=""):
    designators = []

    if not isinstance(cfg, dict):
        return designators

    for key, value in cfg.items():
        key_str = str(key).strip()
        if not key_str:
            continue

        next_prefix = f"{prefix}.{key_str}" if prefix else key_str
        if isinstance(value, dict):
            designators.extend(_flatten_c_designators(value, next_prefix))
        else:
            designators.append((next_prefix, value))

    return designators


def _to_c_initializer_literal(value):
    if isinstance(value, list):
        values = []
        for item in value:
            item_literal = _to_c_initializer_literal(item)
            if item_literal is not None:
                values.append(item_literal)
        return "{" + ", ".join(values) + "}"
    return _to_c_literal(value)


def read_config(config_path, platform):
    yaml_path = _resolve_yaml_config_path(config_path, platform)
    with open(yaml_path, "r") as yaml_file:
        config_file = yaml.safe_load(yaml_file) or {}

    vm_list_config = []
    for vm_idx, vm_entry in enumerate(_extract_vm_entries(config_file)):
        vm_key, vm_cfg = _normalize_vm_entry(vm_entry, vm_idx)
        vm_cfg = vm_cfg if isinstance(vm_cfg, dict) else {}

        vm_runtime_cfg = vm_cfg.get("config", {})
        vm_runtime_cfg = vm_runtime_cfg if isinstance(vm_runtime_cfg, dict) else {}

        vm_list_config.append(
            {
                vm_key: {
                    "name": vm_cfg.get("name"),
                    "build_options": vm_cfg.get("build_options", {}),
                    "image": vm_runtime_cfg.get("image", {}),
                    "entry": vm_runtime_cfg.get("entry"),
                    "platform_cfg": vm_runtime_cfg.get("platform", {}),
                }
            }
        )

    return vm_list_config


def write_config(config_path, platform):
    yaml_path = _resolve_yaml_config_path(config_path, platform)
    platform_name = _get_platform_name(platform)

    with open(yaml_path, "r") as yaml_file:
        # BaseLoader preserves scalar formatting from YAML (for example 0x08000000).
        config_file = yaml.load(yaml_file, Loader=yaml.BaseLoader) or {}

    vm_entries = []
    for vm_idx, vm_entry in enumerate(_extract_vm_entries(config_file)):
        vm_key, vm_cfg = _normalize_vm_entry(vm_entry, vm_idx)
        vm_cfg = vm_cfg if isinstance(vm_cfg, dict) else {}
        vm_runtime_cfg = vm_cfg.get("config", {})
        vm_runtime_cfg = vm_runtime_cfg if isinstance(vm_runtime_cfg, dict) else {}
        vm_image_cfg = vm_runtime_cfg.get("image", {})
        vm_platform_cfg = vm_runtime_cfg.get("platform", {})

        vm_name = vm_cfg.get("name") or vm_key
        build_options = vm_cfg.get("build_options", {})
        build_options = build_options if isinstance(build_options, dict) else {}
        vm_bin_name = build_options.get("bin_name")
        if not isinstance(vm_bin_name, str) or not vm_bin_name.strip():
            vm_bin_name = vm_name
        vm_bin_name = vm_bin_name.strip()
        vm_image_symbol = re.sub(r"[^a-zA-Z0-9_]", "_", f"{vm_bin_name}_image")

        vm_entries.append(
            {
                "name": vm_name,
                "bin_name": vm_bin_name,
                "image_symbol": vm_image_symbol,
                "image": vm_image_cfg if isinstance(vm_image_cfg, dict) else {},
                "entry": vm_runtime_cfg.get("entry"),
                "platform": vm_platform_cfg if isinstance(vm_platform_cfg, dict) else {},
            }
        )

    def image_mode(image_cfg):
        has_base = "base_addr" in image_cfg
        has_load = "load_addr" in image_cfg
        has_phys = "phys_addr" in image_cfg
        has_size = "size" in image_cfg

        if has_load and has_phys and has_size:
            return "loaded"
        if has_base and not has_load and not has_size:
            return "macro_offset_size"
        return "explicit_fields"

    output_lines = ["#include <config.h>", ""]

    image_declared = False
    for vm in vm_entries:
        if image_mode(vm["image"]) == "macro_offset_size":
            output_lines.append(
                f"VM_IMAGE({vm['image_symbol']}, XSTR(BAO_WRKDIR_IMGS/{vm['bin_name']}.bin))"
            )
            image_declared = True

    if image_declared:
        output_lines.append("")

    output_lines.extend(
        [
            "struct config config = {",
            "",
            "    CONFIG_HEADER",
            "",
            f"    .vmlist_size = {len(vm_entries)},",
            "    .vmlist = (struct vm_config[]) {",
        ]
    )

    for vm_idx, vm in enumerate(vm_entries):
        image_cfg = vm["image"]
        platform_cfg = vm["platform"]
        vm_mode = image_mode(image_cfg)

        regions_cfg = platform_cfg.get("regions", [])
        regions_cfg = regions_cfg if isinstance(regions_cfg, list) else []
        devs_cfg = platform_cfg.get("devs", [])
        devs_cfg = devs_cfg if isinstance(devs_cfg, list) else []
        arch_cfg = platform_cfg.get("arch", {})
        arch_cfg = arch_cfg if isinstance(arch_cfg, dict) else {}

        output_lines.append("        {")

        if vm_mode == "loaded":
            load_addr = _to_c_literal(image_cfg.get("load_addr"))
            phys_addr = _to_c_literal(image_cfg.get("phys_addr"))
            image_size = _to_c_literal(image_cfg.get("size"))
            output_lines.append(
                f"            .image = VM_IMAGE_LOADED({load_addr}, {phys_addr}, {image_size}),"
            )
        else:
            if vm_mode == "macro_offset_size":
                load_addr = f"VM_IMAGE_OFFSET({vm['image_symbol']})"
                image_size = f"VM_IMAGE_SIZE({vm['image_symbol']})"
            else:
                load_addr = _to_c_literal(image_cfg.get("load_addr"))
                image_size = _to_c_literal(image_cfg.get("size"))

            if load_addr is None:
                load_addr = f"VM_IMAGE_OFFSET({vm['image_symbol']})"
            if image_size is None:
                image_size = f"VM_IMAGE_SIZE({vm['image_symbol']})"

            base_addr = _to_c_literal(image_cfg.get("base_addr"))
            if base_addr is None:
                base_addr = _to_c_literal(image_cfg.get("phys_addr"))
            if base_addr is None:
                base_addr = load_addr

            output_lines.append("            .image = {")
            _write_field_block(
                output_lines,
                [
                    ("base_addr", base_addr),
                    ("load_addr", load_addr),
                    ("size", image_size),
                ],
                "                ",
            )
            output_lines.append("            },")

        output_lines.append("")
        output_lines.append(f"            .entry = {_to_c_literal(vm['entry'])},")
        output_lines.append("")
        output_lines.append("            .platform = {")
        output_lines.append(f"                .cpu_num = {_to_c_literal(platform_cfg.get('cpu_num'))},")
        output_lines.append("")
        output_lines.append(f"                .region_num = {len(regions_cfg)},")
        output_lines.append("                .regions =  (struct vm_mem_region[]) {")
        for region_idx, region in enumerate(regions_cfg):
            region = region if isinstance(region, dict) else {}
            output_lines.append("                    {")
            _write_field_block(
                output_lines,
                [
                    ("base", _to_c_literal(region.get("base"))),
                    ("size", _to_c_literal(region.get("size"))),
                ],
                "                        ",
            )
            output_lines.append("                    }" + ("," if region_idx < (len(regions_cfg) - 1) else ""))
        output_lines.append("                },")
        output_lines.append("")
        output_lines.append(f"                .dev_num = {len(devs_cfg)},")
        output_lines.append("                .devs =  (struct vm_dev_region[]) {")
        for dev_idx, dev in enumerate(devs_cfg):
            dev = dev if isinstance(dev, dict) else {}
            interrupts = dev.get("interrupts", [])
            interrupts = interrupts if isinstance(interrupts, list) else []
            interrupt_values = ", ".join(_to_c_literal(irq) for irq in interrupts)
            only_interrupts = (
                interrupts
                and "pa" not in dev
                and "va" not in dev
                and "size" not in dev
            )

            output_lines.append("                    {")

            if platform_name == "qemu-aarch64-virt":
                if interrupts == ["33"] and not only_interrupts:
                    output_lines.append("                        /* PL011 */")
                elif interrupts == ["27"] and only_interrupts:
                    output_lines.append("                        /* Arch timer interrupt */")

            if platform_name == "qemu-aarch64-virt" and interrupts == ["27"] and only_interrupts:
                output_lines.append(f"                        .interrupt_num = {len(interrupts)},")
                output_lines.append("                        .interrupts =")
                output_lines.append(f"                            (irqid_t[]) {{{interrupt_values}}}")
            else:
                _write_field_block(
                    output_lines,
                    [
                        ("pa", _to_c_literal(dev.get("pa"))),
                        ("va", _to_c_literal(dev.get("va"))),
                        ("size", _to_c_literal(dev.get("size"))),
                        ("interrupt_num", str(len(interrupts)) if interrupts else None),
                        ("interrupts", f"(irqid_t[]) {{{interrupt_values}}}" if interrupts else None),
                    ],
                    "                        ",
                )
            output_lines.append("                    }" + ("," if dev_idx < (len(devs_cfg) - 1) else ""))
        output_lines.append("                },")

        if arch_cfg:
            output_lines.append("")
            output_lines.append("                .arch = {")
            generic_arch_entries = []
            for arch_key, arch_value in _flatten_c_designators(
                {key: value for key, value in arch_cfg.items() if key != "gic"}
            ):
                arch_literal = _to_c_initializer_literal(arch_value)
                if arch_literal is None:
                    continue
                if platform_name == "qemu-aarch64-virt" and arch_key in {"gic.gicd_addr", "gic.gicr_addr"}:
                    arch_literal = f"(paddr_t) {arch_literal}"
                generic_arch_entries.append((arch_key, arch_literal))

            gic_cfg = arch_cfg.get("gic")
            if isinstance(gic_cfg, dict):
                output_lines.append("                    .gic = {")
                for gic_key, gic_value in gic_cfg.items():
                    gic_literal = _to_c_initializer_literal(gic_value)
                    if gic_literal is None:
                        continue
                    if platform_name == "qemu-aarch64-virt" and gic_key in {"gicd_addr", "gicr_addr"}:
                        gic_literal = f"(paddr_t) {gic_literal}"
                    output_lines.append(f"                        .{gic_key} = {gic_literal},")
                output_lines.append("                    }" + ("," if generic_arch_entries else ""))

            for arch_key, arch_literal in generic_arch_entries:
                output_lines.append(f"                    .{arch_key} = {arch_literal},")
            output_lines.append("                }")

        output_lines.append("            },")
        output_lines.append("        }" + ("," if vm_idx < (len(vm_entries) - 1) else ""))

    output_lines.extend(["    },", "};", ""])

    output_c_path = os.path.splitext(yaml_path)[0] + ".c"
    if os.path.basename(os.path.dirname(yaml_path)) == platform_name:
        output_c_path = os.path.join(os.path.dirname(yaml_path), "config.c")

    with open(output_c_path, "w") as output_file:
        output_file.write("\n".join(output_lines))

    return output_c_path

def launch_tests(tf, tests, platform, wrkdir):
    # Aggregate tests by setup and benchmarks by benchmark name.
    group_key = "benchmark" if tf.run_type == "benchmark" else "setup"
    setup_groups = {}
    for test in tests:
        setup = test.get(group_key) or test.get("setup")
        if setup not in setup_groups:
            setup_groups[setup] = []
        setup_groups[setup].append(test)

    raw_irq_flags = getattr(platform, "irq_flags", {})
    if isinstance(raw_irq_flags, tuple) and len(raw_irq_flags) == 1 and isinstance(raw_irq_flags[0], dict):
        raw_irq_flags = raw_irq_flags[0]
    interrupt_flags = dict(raw_irq_flags) if isinstance(raw_irq_flags, dict) else {}

    for setup, grouped_tests in setup_groups.items():
        test_ids = [test['id'] for test in grouped_tests]
        is_benchmark = tf.run_type == "benchmark"

        if is_benchmark:
            benchmark_name = str(grouped_tests[0].get("benchmark", setup)).strip()
            setup_name = str(grouped_tests[0].get("setup", benchmark_name)).lower()
            setup_cfg_path = os.path.join(BENCHS_DIR, "configs", setup_name)
            if not os.path.isdir(setup_cfg_path):
                raise FileNotFoundError(f"Could not find benchmark config directory '{setup_cfg_path}'.")

            vm_configs = read_config(setup_cfg_path, platform)
            bao_cfg_path_abs = os.path.abspath(setup_cfg_path)
            write_config(setup_cfg_path, platform)
            print_log("INFO", f"Preparing Benchmark IDs {test_ids}: {benchmark_name}.", tab_level=0)
        else:
            setup_name = str(setup).lower()
            setup_cfg_path = os.path.join(TESTS_DIR, "configs", setup_name)
            vm_configs = read_config(setup_cfg_path, platform)
            bao_cfg_path_abs = os.path.abspath(setup_cfg_path)
            write_config(setup_cfg_path, platform)
            print_log(
                "INFO",
                f"Preparing Test IDs {test_ids}: {grouped_tests[0]['suite']} - {grouped_tests[0]['name']} (and others with same setup)...",
                tab_level=0
            )

        tf.hypervisor = tf.runtime_config.get("hypervisor", "bao")
        tf.hypervisor_srcs = tf.runtime_config.get("hypervisor_srcs", "")
        tf.test_config = {
            "platform": _get_platform_name(platform),
            "setup": setup_name,
            "echo": tf.runtime_config.get("echo", "tf"),
            "tests": " ".join(dict.fromkeys(test["name"] for test in grouped_tests if test.get("name"))),
            "suites": " ".join(dict.fromkeys(test["suite"] for test in grouped_tests if test.get("suite"))),
            "benchmark": benchmark_name if is_benchmark else False,
            "vms": vm_configs,
        }

        if "GIC_version" not in interrupt_flags:
            platform_args = tf.runtime_config.get("platform_args", "")
            if isinstance(platform_args, str):
                platform_args = [arg.strip() for arg in platform_args.split(",") if arg.strip()]
            else:
                platform_args = []
            for arg in platform_args:
                if arg.upper().startswith("GICV"):
                    interrupt_flags["GIC_version"] = arg.upper()
                    break

        workload_prefix = "B" if is_benchmark else "T"
        print_log("INFO", f"{workload_prefix}{test_ids}: Building guests ...", tab_level=0)
        tf.build_guests(platform, interrupt_flags)

        print_log("INFO", f"Building run image [{tf.hypervisor}]...", tab_level=0)
        run_bin, bin_name, elf_name = tf.build_run_bin(wrkdir, bao_cfg_path_abs, platform)

        if tf.runtime_config.get("firmware_build", True):
            platform.build_firmware(run_bin, interrupt_flags)

        tf.launch_test(
            run_bin,
            interrupt_flags,
            setup_name,
            tf.runtime_config.get("echo", "tf"),
            platform,
            benchmark_name=benchmark_name if is_benchmark else None
        )

def main():
    print_log("INFO", "Starting test framework...", tab_level=0)
    print_log("INFO", f"Current working directory: {CUR_DIR}", tab_level=1)
    wrkdir = os.path.join(CUR_DIR, "wrkdir")
    os.makedirs(wrkdir, exist_ok=True)

    tf = test_framework(wrkdir)

    print_log("INFO", "Populating tests ...", tab_level=0)
    tf.populate_tests()
    print_log("SUCCESS", "Tests populated.", tab_level=0)

    print_log("INFO", "Populating benchmarks ...", tab_level=0)
    benchmarks = tf.populate_benchmarks()
    if benchmarks:
        print_log("SUCCESS", "Benchmarks populated.", tab_level=0)
    else:
        print_log("WARNING", "No runnable benchmarks discovered.", tab_level=0)

    print_log("INFO", "Populating platforms ...", tab_level=0)
    tf.populate_plats()
    print_log("SUCCESS", f"Platforms populated: {', '.join([plat[0] for plat in tf.plats])}.", tab_level=0)

    print_log("INFO", "Reading TF configuration ...", tab_level=0)
    tf.parse_args()
    print_log("SUCCESS", "Runtime TF configuration built.", tab_level=0)

    print_log("INFO", "Populating guests to build ...", tab_level=0)
    guests = tf.populate_guests(tf.tests_to_run)
    print_log("SUCCESS", f"Guests populated: {', '.join(guests)}.", tab_level=0)

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

    print_log(
        "INFO",
        "Preparing to launch {} IDs {} on platform {}...".format(
            tf.run_type, [test['id'] for test in tf.tests_to_run], tf.runtime_config['platform']
        ),
        tab_level=0
    )
    launch_tests(tf, tf.tests_to_run, plat, wrkdir)

    tf.cleanup()

if __name__ == "__main__":
    main()
