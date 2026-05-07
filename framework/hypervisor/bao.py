import subprocess
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log
from generic import generic_hypervisor



class bao(generic_hypervisor):
    def __init__(self, wrkdir):
        super().__init__(wrkdir)
        self.git_repo = "https://github.com/bao-project/bao-hypervisor.git"
        self.git_rev = "v2.0.0"
    
    def fetch_sources(self, hypervisor_srcs):
        if hypervisor_srcs == "":
            self.srcs_path = os.path.join(self.wrkdir, "hypervisor", "bao")
            self.clone_hypervisor(self.git_repo, self.git_rev, self.srcs_path)
        else:
            self.srcs_path = hypervisor_srcs
            print_log("INFO", f"Using provided hypervisor sources at {self.srcs_path}", tab_level=2)

    def build(self, wrkdir_imgs, config_repo, config_name, platform, env):
        make_cmd = [
            "make",
            f"PLATFORM={platform}",
            f"CONFIG_REPO={config_repo}",
            f"CONFIG={config_name}",
            f"CPPFLAGS=-DBAO_WRKDIR_IMGS={wrkdir_imgs}"
        ]
        print("env in build:", env)
        self.run_cmd(make_cmd, cwd=self.srcs_path, env=env)

        bin_name = "bao.bin"
        elf_name = "bao.elf"
        out_img = os.path.join(self.srcs_path, "bin", platform, platform, bin_name)
        return out_img, bin_name, elf_name

