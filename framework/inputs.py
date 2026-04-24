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
                    help="Comma-separated list of test IDs to execute. If not "
                         "specified, all tests will be executed.")

        parser.add_argument("-x", "--test-exclude",
                    metavar="ID[,ID,...]",
                    help="Assumes all tests are executed, excluding a comma-separated list of test IDs.",
                    default=False)

        parser.add_argument("--no-logger",
                    action="store_true",
                    help="Disables logging functionality",
                    default=False)

        parser.add_argument("-b", "--benchmark",
                    help="Run in benchmark mode",
                    default=" ")

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
        if args.platform.strip() == "":
            raise ValueError("Platform cannot be empty. Please specify a valid platform using the -p or --platform argument.")

        if args.test is not None and args.test_exclude:
            raise ValueError("Cannot specify both --test and --test-exclude arguments. Please choose one or the other.")

        if args.test is not None and args.test != "all":
            test_ids = [test_id.strip() for test_id in args.test.split(",")]
            if not all(test_ids):
                raise ValueError("Test IDs cannot be empty. Please ensure that all test IDs are valid.")
            args.test = test_ids

        if args.test_exclude:
            exclude_ids = [test_id.strip() for test_id in args.test_exclude.split(",")]
            if not all(exclude_ids):
                raise ValueError("Excluded Test IDs cannot be empty. Please ensure that all excluded test IDs are valid.")
            args.test_exclude = exclude_ids

        valid_echo_options = {"full", "tf", "none"}
        if args.echo not in valid_echo_options:
            raise ValueError(f"Invalid echo option '{args.echo}'. Valid options are: {', '.join(valid_echo_options)}.")

        return args
