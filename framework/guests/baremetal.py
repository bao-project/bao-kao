# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import shutil
import subprocess
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

class baremetal:
    def __init__(self, wrkdir, list_tests, list_suites, benchmark, tests_srcs, 
                 bao_tests_path, bin_name, build_flags, local_repo_path=None):
        self.wrkdir = wrkdir
        self.guest_name = "baremetal"

        self.srcs_dir = os.path.join(wrkdir, "guests", self.guest_name)
        self.tests_srcs = tests_srcs
        self.bao_tests_path = bao_tests_path
        self.bin_dir = os.path.join(wrkdir, "guests", "build")

        self.list_tests = list_tests
        self.list_suites = list_suites
        self.build_flags = build_flags
        self.bin_name = bin_name
        self.benchmark = benchmark

        if local_repo_path:
            self.use_local_repo = True
            self.local_repo_path = local_repo_path
        else:
            self.use_local_repo = False

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)

    def run_cmd(self, cmd, cwd=None, env=None):
        p = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # p = subprocess.run(cmd, cwd=cwd, env=env, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def fetch_sources(self):
        """Clone baremetal guest repo if not already present."""
        if not os.path.exists(os.path.join(self.srcs_dir, ".git")):
            print_log("INFO", "Fetching baremetal guest sources...", tab_level=2)

            if self.use_local_repo:
                print_log("INFO", f"Using local repo: {self.local_repo_path}", tab_level=2)
                shutil.copytree(
                    self.local_repo_path,
                    self.srcs_dir,
                    symlinks=True,
                    dirs_exist_ok=True,
                )
            else:
                self.run_cmd(["git", "clone", self.git_url, self.srcs_dir])
                self.run_cmd(["git", "checkout", self.git_rev], cwd=self.srcs_dir)
                self.run_cmd(["git", "submodule", "update", "--init", "--recursive"], cwd=self.srcs_dir)
        else:
            print_log("INFO", f"Guest sources already present.", tab_level=2)
            print("local repo:", self.local_repo_path)
        return self.srcs_dir

class baremetal_test(baremetal):
    def __init__(self, wrkdir, list_tests, list_suites, benchmark, tests_srcs, 
                 bao_tests_path, bin_name, build_flags, local_repo_path=None):
        
        local_repo_path = "/home/diogo/Desktop/bao_dev/test_framework_benchmarks/baremetal_benchmarks/bao-baremetal-test"
        super().__init__(wrkdir, list_tests, list_suites, benchmark, tests_srcs, 
                         bao_tests_path, bin_name, build_flags, local_repo_path)

        self.git_url = "https://github.com/bao-project/bao-baremetal-test.git"
        self.git_rev = "d32ac417fc7057f1ff510d48a35fb8ec0cde79cd"


    def build(self, platform, arch, toolchain, irq_flags, log_level="2"):
        self.fetch_sources()

        # tests_srcs_abs = os.path.abspath(self.tests_srcs)
        bao_tests_abs = os.path.abspath(self.bao_tests_path)
        tests_srcs_abs = os.path.join(bao_tests_abs, "src", "tests")

        tests_src_dst = os.path.join(self.srcs_dir, "tests")
        tests_baotests_dst = os.path.join(tests_src_dst, "bao-tests")

        if os.path.exists(tests_src_dst):
            shutil.rmtree(tests_src_dst)

        os.makedirs(tests_src_dst, exist_ok=True)
        os.makedirs(os.path.join(tests_baotests_dst, "src"), exist_ok=True)

        shutil.copytree(tests_srcs_abs, tests_src_dst, dirs_exist_ok=True)
        bao_tests_src_dir = os.path.join(bao_tests_abs, "src")
        shutil.copytree(bao_tests_src_dir, os.path.join(tests_baotests_dst, "src"), dirs_exist_ok=True)

        print_log("INFO", "Running codegen.py ...", tab_level=1)
        codegen_dir = os.path.join(bao_tests_abs)
        generated_output = os.path.join(tests_baotests_dst, "src", "testf_entry.c")
        self.run_cmd(
            ["python3", "codegen.py", "-dir", tests_srcs_abs, "-o", generated_output],
            cwd=codegen_dir,
        )

        # Build baremetal guest
        print_log("INFO", "Building baremetal guest...", tab_level=1)
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            "BAO_TEST=1",
            "BAREMETAL_TESTS=1",
            f"TESTF_LOG_LEVEL={log_level}",
            f"CROSS_COMPILE={toolchain}",
            f"TESTF_TESTS_DIR={tests_src_dst}",
            f"TESTF_REPO_DIR={tests_baotests_dst}",
        ]

        if self.list_suites:
            make_cmd.append(f'SUITES="{self.list_suites}"')
        if self.list_tests:
            make_cmd.append(f'TESTS="{self.list_tests}"')
        if platform in ["fvp-a", "fvp-r"]:
            make_cmd.append("BAREMETAL_PARAMS=MEM_BASE=0x10000000")

        if arch == "aarch64" and irq_flags:
            gic_version = irq_flags.get("GIC_version", "GICV2")
            make_cmd.append(f"GIC_VERSION={gic_version}")
        
        # make_cmd.append(self.build_flags)
        

        self.run_cmd(make_cmd, cwd=self.srcs_dir)

        # Install artifacts
        out_bin = self.bin_dir
        os.makedirs(out_bin, exist_ok=True)

        built_dir = os.path.join(self.srcs_dir, "build", platform)
        shutil.copy(os.path.join(built_dir, f"{self.guest_name}.bin"),
                    os.path.join(out_bin, f"{self.bin_name}.bin"))
        shutil.copy(os.path.join(built_dir, f"{self.guest_name}.elf"),
                    os.path.join(out_bin, f"{self.bin_name}.elf"))

        print_log("SUCCESS", f"Built baremetal guest stored at {out_bin}", tab_level=1)
        return os.path.join(out_bin, f"{self.bin_name}.bin")
