"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
CLI input parsing and validation for the Bao Kao Framework.
"""

import argparse
import os
from abc import ABC, abstractmethod


def _serial_port(value):
    """Normalize and validate a serial port CLI value."""
    port = value.strip()
    if not port:
        raise argparse.ArgumentTypeError("serial port path cannot be empty")
    return port


class InputProvider(ABC):  # pylint: disable=too-few-public-methods
    """Interface for runtime configuration providers."""

    @abstractmethod
    def kao_config(self, platforms=None):
        """Return validated runtime arguments."""


class CLI(InputProvider):
    """Command-line input provider."""

    @staticmethod
    def wrkdir():
        """Read the working directory before parsing the full CLI."""
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument(
            "--wrkdir",
            default=os.path.join(os.getcwd(), "wrkdir"),
        )
        args, _ = parser.parse_known_args()
        return os.path.abspath(args.wrkdir)

    def kao_config(self, platforms=None):
        """Parse and validate framework CLI arguments."""
        parser = argparse.ArgumentParser(
            description="Bao Kao Testing Framework",
            formatter_class=argparse.RawTextHelpFormatter,
        )

        parser.add_argument(
            "-l",
            "--log-level",
            help=(
                "Amount of information produced by the framework:\n"
                "0 - only logs the final report\n"
                "1 - logs failed tests and the final report\n"
                "2 - logs all test results and the final report"
            ),
            default=0,
        )

        parser.add_argument(
            "-e",
            "--echo",
            help=(
                "Output filtering mode:\n"
                "full - does not filter any information\n"
                "tf   - filters logging not produced by the framework\n"
                "none - filter every logging"
            ),
            default="tf",
        )

        plat_lst = ""
        if platforms:
            plat_lst += f"\nAvailable: {', '.join(platforms)}"

        parser.add_argument(
            "-p",
            "--platform",
            help="Target platform to run the tests/benchmarks on" + plat_lst,
            required=True,
            default="",
        )

        parser.add_argument(
            "--plat-virt-args",
            metavar="ARG1,ARG2,...",
            required=False,
            help=(
                "Additional platform-specific arguments for the virtual "
                "platforms, provided as a comma-separated list.\n"
                'For example: --plat-virt-args="GICV3"'
            ),
            default="",
        )

        parser.add_argument(
            "--serial-port",
            action="append",
            type=_serial_port,
            metavar="PATH",
            help=(
                "Override a physical platform's default serial port. "
                "Repeat this option for platforms that use multiple ports."
            ),
            default=None,
        )

        parser.add_argument(
            "-t",
            "--test",
            metavar="ID[,ID,...]",
            nargs="?",
            const="all",
            default=None,
            help=(
                "Comma-separated list of test IDs to execute, exactly as written in "
                "the BAO_TEST registrations. If --test is provided without IDs, all "
                "discovered tests are selected.\n"
                "Combine with --tags, --exclude-tags, --env and --test-exclude "
                "to narrow the selection."
            ),
        )

        parser.add_argument(
            "-x",
            "--test-exclude",
            metavar="ID[,ID,...]",
            help=(
                "Comma-separated list of test IDs to exclude from the selected tests.\n"
                "Can be combined with --test (including bare --test, "
                "which means all tests)."
            ),
            default=False,
        )

        parser.add_argument(
            "--tags",
            metavar="TAG[,TAG,...]",
            help=(
                "Comma-separated list of tags. Only tests carrying all of them "
                "are selected."
            ),
            default=None,
        )

        parser.add_argument(
            "--exclude-tags",
            metavar="TAG[,TAG,...]",
            help="Comma-separated list of tags. Tests carrying any of them are excluded.",
            default=None,
        )

        parser.add_argument(
            "--env",
            metavar="ENV[,ENV,...]",
            help=(
                "Comma-separated list of environments to run in. By default a test "
                "runs in every environment it declares that the platform provides."
            ),
            default=None,
        )

        parser.add_argument(
            "--no-logger",
            action="store_true",
            help="Disables logging functionality",
            default=False,
        )

        parser.add_argument(
            "-b",
            "--benchmark",
            metavar="ID[,ID,...]",
            nargs="?",
            const="all",
            default=None,
            help=(
                "Comma-separated list of benchmark IDs to execute. If --benchmark "
                "is provided without IDs, all discovered benchmarks are executed."
            ),
        )

        parser.add_argument(
            "--benchmark-exclude",
            metavar="ID[,ID,...]",
            help=(
                "Assumes all benchmarks are executed, excluding a comma-separated "
                "list of benchmark IDs."
            ),
            default=False,
        )

        parser.add_argument(
            "--generate-id-readme",
            metavar="PATH",
            nargs="?",
            const="README.workload-ids.md",
            default=None,
            help=(
                "Generate a Markdown file mapping discovered test and benchmark "
                "IDs, then exit.\n"
                "If PATH is omitted, writes to README.workload-ids.md"
            ),
        )

        parser.add_argument(
            "--no-firmware-build",
            action="store_true",
            help="Skips firmware build phase, assuming pre-built firmware is available",
            default=False,
        )

        parser.add_argument(
            "--no-toolchain-build",
            action="store_true",
            help="Skips toolchain download/build phase",
            default=False,
        )

        parser.add_argument(
            "-H",
            "--hypervisor",
            metavar="<bao|none>",
            required=False,
            help=(
                "Hypervisor mode to use (default: bao):\n"
                "bao  - build/run with Bao hypervisor\n"
                "none - run directly on platform without hypervisor\n"
                "Note: 'standalone' is accepted as a deprecated alias for 'none'."
            ),
            default="bao",
        )

        parser.add_argument(
            "--hyp-srcs",
            required=False,
            metavar="PATH",
            help=(
                "Path to hypervisor sources. Without -H argument, we assume "
                "that the sources are related to bao hypervisor."
            ),
            default="",
        )

        parser.add_argument(
            "--wrkdir",
            metavar="PATH",
            help="Directory used for generated sources and build artifacts",
            default=os.path.join(os.getcwd(), "wrkdir"),
        )

        parser.add_argument(
            "--tests-root",
            metavar="DIR",
            help=(
                "Directory holding the project's tests: src/ with the test sources "
                "and configs/ with the environments (default: ../tests relative to kao)"
            ),
            default=None,
        )

        parser.add_argument(
            "--tests-src",
            metavar="DIR|FILE",
            action="append",
            help=(
                "Test sources to scan, under <tests-root>/src: a directory (scanned "
                "non-recursively) or a file. Repeat for several. Without it the whole "
                "src/ tree is scanned."
            ),
            default=None,
        )

        parser.add_argument(
            "--configs",
            metavar="DIR",
            help="Directory holding the environment configs (default: <tests-root>/configs)",
            default=None,
        )

        args = parser.parse_args()
        return self.validate_args(args)

    @staticmethod
    def validate_args(args):
        """Validate parsed CLI args and normalize values."""

        def parse_csv_ids(csv_value, label):
            ids = [entry.strip() for entry in csv_value.split(",")]
            if not all(ids):
                raise ValueError(
                    f"{label} IDs cannot be empty. Please ensure all "
                    f"{label.lower()} IDs are valid."
                )
            return ids

        if args.platform.strip() == "":
            raise ValueError(
                "Platform cannot be empty. Please specify a valid platform "
                "using the -p or --platform argument."
            )

        if args.benchmark is not None and args.benchmark_exclude:
            raise ValueError(
                "Cannot specify both --benchmark and --benchmark-exclude "
                "arguments. Please choose one or the other."
            )

        test_filters_requested = any(
            value is not None for value in (args.tags, args.exclude_tags, args.env)
        )
        test_mode_requested = (
            args.test is not None or bool(args.test_exclude) or test_filters_requested
        )
        benchmark_mode_requested = args.benchmark is not None or bool(args.benchmark_exclude)
        if test_mode_requested and benchmark_mode_requested:
            raise ValueError(
                "Cannot combine test and benchmark selection arguments. "
                "Please choose either tests or benchmarks."
            )

        if args.test is not None and args.test != "all":
            args.test = parse_csv_ids(args.test, "Test")

        if args.test_exclude:
            args.test_exclude = parse_csv_ids(args.test_exclude, "Excluded Test")

        def parse_csv_tokens(csv_value, label):
            if csv_value is None:
                return None
            tokens = [entry.strip().lower() for entry in csv_value.split(",")]
            if not all(tokens):
                raise ValueError(f"{label} list contains an empty entry.")
            return tokens

        for attr, label in (
            ("tags", "Tag"),
            ("exclude_tags", "Excluded tag"),
            ("env", "Environment"),
        ):
            setattr(args, attr, parse_csv_tokens(getattr(args, attr), label))

        if args.benchmark is not None and args.benchmark != "all":
            args.benchmark = parse_csv_ids(args.benchmark, "Benchmark")

        if args.benchmark_exclude:
            args.benchmark_exclude = parse_csv_ids(
                args.benchmark_exclude,
                "Excluded Benchmark",
            )

        valid_echo_options = {"full", "tf", "none"}
        if args.echo not in valid_echo_options:
            raise ValueError(
                f"Invalid echo option '{args.echo}'. Valid options are: "
                f"{', '.join(valid_echo_options)}."
            )

        hypervisor = str(args.hypervisor).strip().lower()
        if hypervisor == "standalone":
            hypervisor = "none"

        valid_hypervisors = {"bao", "none"}
        if hypervisor not in valid_hypervisors:
            raise ValueError(
                f"Invalid hypervisor '{args.hypervisor}'. Valid options are: "
                f"{', '.join(sorted(valid_hypervisors))}."
            )
        args.hypervisor = hypervisor

        if hypervisor == "bao" and not args.hyp_srcs:
            raise ValueError(
                "Bao hypervisor sources must be provided using --hyp-srcs."
            )

        return args
