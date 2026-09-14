"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Baremetal guest build helpers.
"""

from __future__ import annotations

import importlib
import os
import shlex
import sys
import shutil

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CUR_DIR, "../"))
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

from utils.process import run_cmd  # pylint: disable=wrong-import-position,import-error
from utils.codegen import (  # pylint: disable=wrong-import-position,import-error
    parse_discovery,
    write_all_source,
    write_tests_source,
)
print_log = getattr(importlib.import_module("constants"), "print_log")


class Baremetal:  # pylint: disable=too-many-instance-attributes
    """Base helper for Bao baremetal guest sources and builds."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        wrkdir,
        tests,
        benchmark,
        kao_dir,
        tests_srcs,
        bin_name,
        build_flags,
        local_repo_path=None,
    ):
        """Initialize baremetal guest paths, sources, and build options."""
        self.wrkdir = wrkdir
        self.guest_name = "baremetal"

        self.srcs_dir = os.path.join(wrkdir, "guests", self.guest_name)
        self.kao_dir = kao_dir
        self.tests_srcs = os.path.abspath(tests_srcs)
        self.bin_dir = os.path.join(wrkdir, "guests", "build")

        self.tests = tests
        self.build_flags = build_flags
        self.bin_name = bin_name
        self.benchmark = benchmark

        self.git_url = "https://github.com/bao-project/bao-baremetal-test.git"
        self.git_rev = "2b14d908026f18254333230d457fb8f04d4a6ff4"

        self.use_local_repo = bool(local_repo_path)
        self.local_repo_path = local_repo_path
        self.make_cmd = None

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)

    def fetch_sources(self):
        """Clone the baremetal guest repository if it is not already present."""
        git_dir = os.path.join(self.srcs_dir, ".git")
        if os.path.exists(git_dir):
            print_log("INFO", "Guest sources already present.", tab_level=2)
            return self.srcs_dir

        print_log("INFO", "Fetching baremetal guest sources...", tab_level=2)

        if self.use_local_repo:
            print_log("INFO", f"Using local repo: {self.local_repo_path}", tab_level=2)
            shutil.copytree(
                self.local_repo_path,
                self.srcs_dir,
                symlinks=True,
                dirs_exist_ok=True,
            )
            return self.srcs_dir

        run_cmd(["git", "clone", self.git_url, self.srcs_dir])
        run_cmd(["git", "checkout", self.git_rev], cwd=self.srcs_dir)
        run_cmd(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=self.srcs_dir,
        )
        return self.srcs_dir

    def clean(self):
        """Clean the baremetal guest build artifacts."""
        if os.path.exists(self.bin_dir):
            shutil.rmtree(self.bin_dir)


class BaremetalTest(Baremetal):
    """Builder for Bao baremetal test guests.

    The guest is built in place: TESTF_TESTS_DIR points at kao's hook folder for
    this guest (which pulls in the shared harness and headers), the project's
    test sources are included from where they live, and only the files kao
    generates go to the work directory.
    """

    @property
    def hook_dir(self):
        """kao's hook folder for this guest, laid out as the guest expects it."""
        return os.path.join(self.kao_dir, "kao", "guests", "baremetal")

    @property
    def gen_dir(self):
        """Where kao writes kao_all.c and kao_tests.c."""
        return os.path.join(self.wrkdir, "guests", "kao")

    def _build_make_cmd(  # pylint: disable=too-many-arguments
        self, platform, arch, toolchain, irq_flags, log_level
    ):
        """Construct the make command for the baremetal guest build."""
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            "BAREMETAL_TESTS=1",
            f"CROSS_COMPILE={toolchain}",
            f"NAME={self.bin_name}",
            f"BUILD_DIR={self.bin_dir}",
            f"TESTF_TESTS_DIR={self.hook_dir}",
            f"KAO_GEN_DIR={self.gen_dir}",
            f"KAO_LOG_LEVEL={log_level}",
        ]

        if arch == "aarch64":
            gic_version = (irq_flags or {}).get("GIC_version", "GICV3")
            make_cmd.append(f"GIC_VERSION={gic_version}")

        generic_flags = self.build_flags.get("generic_flags")
        cpu_num = self.build_flags.get("cpu_num")

        if generic_flags:
            make_cmd.extend(shlex.split(generic_flags))
        if cpu_num:
            make_cmd.append(f"NUM_CPUS={cpu_num}")

        return make_cmd

    def prepare(  # pylint: disable=too-many-arguments
        self,
        platform,
        arch,
        toolchain,
        irq_flags,
        log_level="2",
    ):
        """Fetch the guest and fix the make invocation."""
        self.fetch_sources()
        self.make_cmd = self._build_make_cmd(platform, arch, toolchain, irq_flags, log_level)

    def discover(self, files):
        """Return the tests registered in the given sources (paths under src/)."""
        print_log("INFO", "Discovering tests ...", tab_level=1)
        write_all_source(files, self.tests_srcs, self.gen_dir)
        output = run_cmd(self.make_cmd + ["kao-discover"], cwd=self.srcs_dir)
        return parse_discovery(output, self.tests_srcs)

    def build(  # pylint: disable=too-many-arguments
        self,
        platform,
        arch,
        toolchain,
        irq_flags,
        log_level="2",
    ):
        """Build the baremetal test guest and return the output binary path."""
        self.prepare(platform, arch, toolchain, irq_flags, log_level)
        write_tests_source(self.tests, self.tests_srcs, self.gen_dir)

        print_log("INFO", "Building baremetal guest...", tab_level=1)
        run_cmd(self.make_cmd, cwd=self.srcs_dir)

        out_bin_path = os.path.join(self.bin_dir, f"{self.bin_name}.bin")
        print_log("INFO", f"Built baremetal guest stored at {out_bin_path}", tab_level=1)
        return out_bin_path


baremetal = Baremetal  # pylint: disable=invalid-name
baremetal_test = BaremetalTest  # pylint: disable=invalid-name
