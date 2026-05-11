import subprocess
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log

class generic_hypervisor:
    def __init__(self, wrkdir, srcs_path=""):
        self.wrkdir = wrkdir
        self.srcs_path = srcs_path
        self.git_repo = ""
        self.git_rev = ""


    def run_cmd(self, cmd, cwd=None, env=None):
        p = subprocess.run(cmd, cwd=cwd, env=env, text=True)
        print("env:", env)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
        
    def fetch_sources(self, hypervisor_srcs):
        pass

    def clone_hypervisor(self, git_repo, git_rev, srcs_path):
        if not os.path.exists(os.path.join(self.srcs_path, ".git")):
            print_log("INFO", f"Fetching hypervisor sources...", tab_level=2)
            self.run_cmd(["git", "clone", git_repo, srcs_path])
            self.run_cmd(["git", "checkout", git_rev], cwd=srcs_path)
        else:
            print_log("INFO", f"Hypervisor sources already present.", tab_level=2)

    def clean(self, directory):
        make_cmd = ["make", "clean"]
        self.run_cmd(make_cmd, cwd=directory)

class standalone(generic_hypervisor):
    def __init__(self):
        super().__init__()

    def build(self, wrkdir_imgs, config_repo, config_name, platform, env):
        bin_name = "guest_1.bin"
        elf_name = "guest_1.elf"
        out_img = os.path.join(wrkdir_imgs, bin_name)
        return out_img, bin_name, elf_name

    def clean(self, directory):
        pass
