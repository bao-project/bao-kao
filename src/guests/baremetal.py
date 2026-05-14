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
print_log = getattr(importlib.import_module("constants"), "print_log")


class Baremetal:  # pylint: disable=too-many-instance-attributes
    """Base helper for Bao baremetal guest sources and builds."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        wrkdir,
        list_tests,
        list_suites,
        benchmark,
        bkao_dir,
        tests_srcs,
        bin_name,
        build_flags,
        local_repo_path=None,
    ):
        """Initialize baremetal guest paths, sources, and build options."""
        self.wrkdir = wrkdir
        self.guest_name = "baremetal"

        self.srcs_dir = os.path.join(wrkdir, "guests", self.guest_name)
        self.bkao_dir = bkao_dir
        self.tests_srcs = tests_srcs
        self.bin_dir = os.path.join(wrkdir, "guests", "build")

        self.list_tests = list_tests
        self.list_suites = list_suites
        self.build_flags = build_flags
        self.bin_name = bin_name
        self.benchmark = benchmark

        self.git_url = "https://github.com/bao-project/bao-baremetal-test.git"
        self.git_rev = "80dd17bd45fef1024f59f08b7e7bc69c9336a203"

        self.use_local_repo = bool(local_repo_path)
        self.local_repo_path = local_repo_path

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
        if os.path.exists(self.srcs_dir):
            run_cmd(["make", "clean"], cwd=self.srcs_dir)
        if os.path.exists(self.bin_dir):
            shutil.rmtree(self.bin_dir)


class BaremetalTest(Baremetal):
    """Builder for Bao baremetal test guests."""

    @staticmethod
    def _prepare_tests_tree(srcs_dir, tests_srcs_abs):
        """Refresh the local tests tree used by the guest build."""
        tests_dst = os.path.join(srcs_dir, "tests")
        if os.path.exists(tests_dst):
            shutil.rmtree(tests_dst)

        os.makedirs(tests_dst, exist_ok=True)

        bao_tests_src_dir = os.path.join(tests_srcs_abs, "src")
        shutil.copytree(
            bao_tests_src_dir,
            os.path.join(tests_dst, "src"),
            dirs_exist_ok=True,
        )
        return tests_dst

    def _run_codegen(self, tests_srcs_abs, tests_dst):
        """Generate the consolidated test entry source file."""
        print_log("INFO", "Running codegen.py ...", tab_level=1)
        codegen_dir = os.path.join(self.bkao_dir, "utils")
        generated_output = os.path.join(tests_dst, "src", "testf_entry.c")
        run_cmd(
            ["python3", "codegen.py", "-dir", tests_srcs_abs, "-o", generated_output],
            cwd=codegen_dir,
        )

    def _build_make_cmd(  # pylint: disable=too-many-arguments
        self, platform, arch, toolchain, irq_flags, log_level, tests_dst
    ):
        """Construct the make command for the baremetal guest build."""
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            "BAO_TEST=1",
            "BAREMETAL_TESTS=1",
            f"TESTF_LOG_LEVEL={log_level}",
            f"CROSS_COMPILE={toolchain}",
            f"TESTF_TESTS_DIR={tests_dst}",
        ]

        if self.list_tests:
            tests = " ".join(str(self.list_tests).split())
            if tests:
                make_cmd.append(f"TESTS={tests}")
        elif self.list_suites:
            suites = " ".join(str(self.list_suites).split())
            if suites:
                make_cmd.append(f"SUITES={suites}")

        if arch == "aarch64" and irq_flags:
            gic_version = irq_flags.get("GIC_version", "GICV3")
            make_cmd.append(f"GIC_VERSION={gic_version}")

        generic_flags = self.build_flags.get("generic_flags")
        cpu_num = self.build_flags.get("cpu_num")

        if generic_flags:
            make_cmd.extend(shlex.split(generic_flags))
        if cpu_num:
            make_cmd.append(f"NUM_CPUS={cpu_num}")

        return make_cmd

    def _copy_build_outputs(self, platform):
        """Copy generated guest artifacts to the framework output directory."""
        os.makedirs(self.bin_dir, exist_ok=True)

        built_dir = os.path.join(self.srcs_dir, "build", platform)
        out_bin_path = os.path.join(self.bin_dir, f"{self.bin_name}.bin")
        out_elf_path = os.path.join(self.bin_dir, f"{self.bin_name}.elf")

        shutil.copy(
            os.path.join(built_dir, f"{self.guest_name}.bin"),
            out_bin_path,
        )
        shutil.copy(
            os.path.join(built_dir, f"{self.guest_name}.elf"),
            out_elf_path,
        )
        return out_bin_path

    def build(  # pylint: disable=too-many-arguments
        self,
        platform,
        arch,
        toolchain,
        irq_flags,
        log_level="2",
    ):
        """Build the baremetal test guest and return the output binary path."""
        self.fetch_sources()

        tests_srcs_abs = os.path.abspath(self.tests_srcs)
        tests_dst = self._prepare_tests_tree(self.srcs_dir, tests_srcs_abs)
        self._run_codegen(tests_srcs_abs, tests_dst)

        print_log("INFO", "Building baremetal guest...", tab_level=1)
        make_cmd = self._build_make_cmd(
            platform,
            arch,
            toolchain,
            irq_flags,
            log_level,
            tests_dst,
        )

        run_cmd(make_cmd, cwd=self.srcs_dir)

        out_bin_path = self._copy_build_outputs(platform)
        print_log(
            "SUCCESS",
            f"Built baremetal guest stored at {self.bin_dir}",
            tab_level=1,
        )
        return out_bin_path


baremetal = Baremetal  # pylint: disable=invalid-name
baremetal_test = BaremetalTest  # pylint: disable=invalid-name
