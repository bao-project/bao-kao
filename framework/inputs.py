# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import argparse
from abc import ABC, abstractmethod

class InputProvider(ABC):
    @abstractmethod
    def tf_config(self, platforms=None):
        pass

class CLI(InputProvider):
    def tf_config(self, platforms=None):
        parser = argparse.ArgumentParser(description="Bao Testing Framework",
                                         formatter_class=argparse.RawTextHelpFormatter)

        parser.add_argument("-l", "--log-level",
                    help="Amount of information produced by the framework:\n"
                         "0 - only logs the final report\n"
                         "1 - logs failed tests and the final report\n"
                         "2 - logs all test results and the final report",
                    default=0)

        parser.add_argument("-e", "--echo",
                    help="Output filtering mode:\n"
                         "full - does not filter any information\n"
                         "tf   - filters logging not produced by the framework\n"
                         "none - filter every logging",
                    default="tf")

        plat_lst = ""
        if platforms:
            plat_lst += f"\nAvailable: {', '.join(platforms)}"

        parser.add_argument("-p", "--platform",
                    help="Target platform to run the tests/benchmarks on" + plat_lst,
                    required=True,
                    default="")

        parser.add_argument("--plat-virt-args",
                    metavar="ARG1,ARG2,...",
                    required=False,
                    help="Additional platform-specific arguments for the virtual platforms"
                         ", provided as a comma-separated list.\n"
                         "For example: --plat-virt-args=\"GICV3\"",
                    default="")

        parser.add_argument("-t", "--test",
                    metavar="ID[,ID,...]",
                    nargs="?",
                    const="all",
                    default=None,
                    help="Comma-separated list of test IDs to execute. If --test "
                         "is provided without IDs, all discovered tests are executed.")

        parser.add_argument("-x", "--test-exclude",
                    metavar="ID[,ID,...]",
                    help="Assumes all tests are executed, excluding a comma-separated list of test IDs.",
                    default=False)

        parser.add_argument("--no-logger",
                    action="store_true",
                    help="Disables logging functionality",
                    default=False)

        parser.add_argument("-b", "--benchmark",
                    metavar="ID[,ID,...]",
                    nargs="?",
                    const="all",
                    default=None,
                    help="Comma-separated list of benchmark IDs to execute. If --benchmark "
                         "is provided without IDs, all discovered benchmarks are executed.")

        parser.add_argument("--benchmark-exclude",
                    metavar="ID[,ID,...]",
                    help="Assumes all benchmarks are executed, excluding a comma-separated list of benchmark IDs.",
                    default=False)

        parser.add_argument("--generate-id-readme",
                    metavar="PATH",
                    nargs="?",
                    const="README.workload-ids.md",
                    default=None,
                    help="Generate a Markdown file mapping discovered test and benchmark IDs, then exit.\n"
                         "If PATH is omitted, writes to README.workload-ids.md")

        parser.add_argument("--no-firmware-build",
                    action="store_true",
                    help="Skips firmware build phase, assuming pre-built firmware is available",
                    default=False)

        parser.add_argument("--no-toolchain-build",
                    action="store_true",
                    help="Skips toolchain download/build phase",
                    default=False)

        parser.add_argument("-H", "--hypervisor",
                    metavar="<bao>",
                    required=False,
                    help="Hypervisor to use (default: bao). Currently, only bao is supported.",
                    default="bao")

        parser.add_argument("--hyp-srcs",
                    required=False,
                    metavar="PATH",
                    help="Path to hypervisor sources. Without -H argument, we assume that"
                         " the sources are related to bao hypervisor.",
                    default="")

        args = parser.parse_args()

        validated_args = self.validate_args(args)

        return validated_args

    def validate_args(self, args):
        def parse_csv_ids(csv_value, label):
            ids = [entry.strip() for entry in csv_value.split(",")]
            if not all(ids):
                raise ValueError(f"{label} IDs cannot be empty. Please ensure that all {label.lower()} IDs are valid.")
            return ids

        if args.platform.strip() == "":
            raise ValueError("Platform cannot be empty. Please specify a valid platform using the -p or --platform argument.")

        if args.test is not None and args.test_exclude:
            raise ValueError("Cannot specify both --test and --test-exclude arguments. Please choose one or the other.")

        if args.benchmark is not None and args.benchmark_exclude:
            raise ValueError("Cannot specify both --benchmark and --benchmark-exclude arguments. Please choose one or the other.")

        test_mode_requested = args.test is not None or bool(args.test_exclude)
        benchmark_mode_requested = args.benchmark is not None or bool(args.benchmark_exclude)
        if test_mode_requested and benchmark_mode_requested:
            raise ValueError("Cannot combine test and benchmark selection arguments. Please choose either tests or benchmarks.")

        if args.test is not None and args.test != "all":
            args.test = parse_csv_ids(args.test, "Test")

        if args.test_exclude:
            args.test_exclude = parse_csv_ids(args.test_exclude, "Excluded Test")

        if args.benchmark is not None and args.benchmark != "all":
            args.benchmark = parse_csv_ids(args.benchmark, "Benchmark")

        if args.benchmark_exclude:
            args.benchmark_exclude = parse_csv_ids(args.benchmark_exclude, "Excluded Benchmark")

        valid_echo_options = {"full", "tf", "none"}
        if args.echo not in valid_echo_options:
            raise ValueError(f"Invalid echo option '{args.echo}'. Valid options are: {', '.join(valid_echo_options)}.")

        return args
