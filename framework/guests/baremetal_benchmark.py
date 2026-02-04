# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved.

import os
import shutil
import subprocess


class baremetal_benchmark:
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

        self.use_local_repo = True  # ← flip to True for local testing
        self.local_repo_path = "/home/mafs/MISRA/bao-baremetal-test"

        os.makedirs(self.srcs_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)

        self.git_url = "https://github.com/miguelafsilva5/bao-baremetal-bench.git"
        self.git_rev = "85b9f277b4944931bcdeb447565a755c22323d10"

    def run_cmd(self, cmd, cwd=None, env=None):
        print(f"COMMAND:", cmd)
        p = subprocess.run(cmd, cwd=cwd, env=env)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")

    def fetch_sources(self):
        """Clone baremetal guest repo if not already present."""
        if not os.path.exists(os.path.join(self.srcs_dir, ".git")):
            print("[INFO] Fetching baremetal guest sources...")

            if self.use_local_repo:
                print(f"[INFO] Using local repo: {self.local_repo_path}")
                shutil.copytree(
                    self.local_repo_path,
                    self.srcs_dir,
                    symlinks=True,
                    dirs_exist_ok=True,
                )
            else:
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

        #print("[INFO] Running codegen.py ...")
        #codegen_dir = os.path.join(bao_tests_abs, "framework")
        #generated_output = os.path.join(tests_baotests_dst, "src", "testf_entry.c")
        #self.run_cmd(
        #    ["python3", "codegen.py", "-dir", tests_srcs_abs, "-o", generated_output],
        #    cwd=codegen_dir,
        #)

        # Build baremetal guest
        print("[INFO] Guest repo name/bin_name still needs to be changed!")
        print("[INFO] Building baremetal-benchmark guest...")
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            f"CROSS_COMPILE={toolchain}",
        ]

        #if self.list_suites:
        #    make_cmd.append(f'SUITES="{self.list_suites}"')
        #if self.list_tests:
        #    make_cmd.append(f'TESTS="{self.list_tests}"')
        #if platform in ["fvp-a", "fvp-r"]:
        #    make_cmd.append("BAREMETAL_PARAMS=MEM_BASE=0x10000000")

        #if arch == "aarch64" and irq_flags:
        #    gic_version = irq_flags.get("GIC_version", "GICV2")
        #    make_cmd.append(f"GIC_VERSION={gic_version}")
        
        make_cmd.extend([
            "BAREMETAL_BENCHMARKS=1",
            "BENCHMARK=irq-lat",
        ])

        env = os.environ.copy()

        if self.build_flags:
            for item in self.build_flags.split():
                k, v = item.split("=", 1)
                env[k] = v


        self.run_cmd(make_cmd, cwd=self.srcs_dir, env=env)

        # Install artifacts
        out_bin = self.bin_dir
        os.makedirs(out_bin, exist_ok=True)

        built_dir = os.path.join(self.srcs_dir, "build", self.guest_name)

        print("[INFO] out_bin ", out_bin)
        print("[INFO] built_dir ", built_dir)
        print("[INFO] bin_name ", self.bin_name)
        print("[INFO] guest_name ", self.guest_name)

        shutil.copy(os.path.join(built_dir, f"{self.guest_name}.bin"),
                    os.path.join(out_bin, f"{self.bin_name}.bin"))
        shutil.copy(os.path.join(built_dir, f"{self.guest_name}.elf"),
                    os.path.join(out_bin, f"{self.bin_name}.elf"))

        print(f"[INFO] Built baremetal guest stored at {out_bin}")
        return os.path.join(out_bin, f"{self.bin_name}.bin")
