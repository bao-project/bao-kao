# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import shutil
import subprocess


class baremetal:
    def __init__(self, wrkdir, list_tests, list_suites, tests_srcs, bao_tests_path, bin_name, build_flags):
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

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)

        self.git_url = "https://github.com/bao-project/bao-baremetal-test.git"
        self.git_rev = "d32ac417fc7057f1ff510d48a35fb8ec0cde79cd"

    def run_cmd(self, cmd, cwd=None):
        p = subprocess.run(cmd, cwd=cwd)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def fetch_sources(self):
        """Clone baremetal guest repo if not already present."""
        if not os.path.exists(os.path.join(self.srcs_dir, ".git")):
            print("[INFO] Fetching baremetal guest sources...")
            self.run_cmd(["git", "clone", "--recursive", self.git_url, self.srcs_dir])
            self.run_cmd(["git", "checkout", self.git_rev], cwd=self.srcs_dir)
        else:
            print("[INFO] Guest sources already present.")
        return self.srcs_dir

    def build(self, platform, arch, toolchain, irq_flags, log_level="2"):
        self.fetch_sources()

        tests_srcs_abs = os.path.abspath(self.tests_srcs)
        bao_tests_abs = os.path.abspath(self.bao_tests_path)


        tests_root = os.path.join(self.srcs_dir, "tests")
        tests_src_dst = tests_root
        tests_baotests_dst = os.path.join(tests_root, "bao-tests")


        if os.path.exists(tests_root):
            shutil.rmtree(tests_root)
        os.makedirs(tests_src_dst, exist_ok=True)
        os.makedirs(os.path.join(tests_baotests_dst, "src"), exist_ok=True)

        # Copy external tests into tests/
        shutil.copytree(tests_srcs_abs, tests_src_dst, dirs_exist_ok=True)
        bao_tests_src_dir = os.path.join(bao_tests_abs, "src")
        shutil.copytree(bao_tests_src_dir, os.path.join(tests_baotests_dst, "src"), dirs_exist_ok=True)

        print("[INFO] Running codegen.py ...")
        codegen_dir = os.path.join(bao_tests_abs, "framework")
        generated_output = os.path.join(tests_baotests_dst, "src", "testf_entry.c")
        self.run_cmd(
            ["python3", "codegen.py", "-dir", tests_srcs_abs, "-o", generated_output],
            cwd=codegen_dir,
        )

        # Build baremetal guest
        print("[INFO] Building baremetal guest...")
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            "BAO_TEST=1",
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
        
        make_cmd.append(self.build_flags)

        self.run_cmd(make_cmd, cwd=self.srcs_dir)

        # Install artifacts
        out_bin = self.bin_dir
        os.makedirs(out_bin, exist_ok=True)

        built_dir = os.path.join(self.srcs_dir, "build", platform)
        shutil.copy(os.path.join(built_dir, f"{self.guest_name}.bin"),
                    os.path.join(out_bin, f"{self.bin_name}.bin"))
        shutil.copy(os.path.join(built_dir, f"{self.guest_name}.elf"),
                    os.path.join(out_bin, f"{self.bin_name}.elf"))

        print(f"[INFO] Built baremetal guest stored at {out_bin}")
        return os.path.join(out_bin, f"{self.bin_name}.bin")
