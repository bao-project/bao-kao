import socket
import subprocess
import sys
import os

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log


class generic_platform:
    def __init__(self, wrkdir):
        self.name = "generic_platform"
    
    def run_command(self, command, log_tab_level=0, cwd=None):
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print_log("[INFO]", f"Running command: {' '.join(command)}", tab_level=log_tab_level)
        print_log("[OUTPUT]", f"stdout: {result.stdout}", tab_level=log_tab_level + 1)
        if result.returncode != 0:
            print_log("[ERROR]", f"Command '{' '.join(command)}'", tab_level=log_tab_level + 1)
            print_log("[ERROR]", f"failed with error:\n{result.stderr}", tab_level=log_tab_level + 2)
            # print(f"[ERROR] Command '{' '.join(command)}' failed with error:\n{result.stderr}")
            raise Exception(f"Command '{' '.join(command)}' failed")
        return result.stdout
    

class generic_emulator(generic_platform):
    def __init__(self, wrkdir):
        self.name = "emulator"

    def check_port_in_use(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
        
    def scan_pts_ports(self):
        """
        Scan available pts ports
        """
        std_out = subprocess.run(['ls', '/dev/pts/'],
                                stdout=subprocess.PIPE,
                                check=True)
        std_out = std_out.stdout.decode('ASCII')
        ports = std_out.split()
        return ports

    def diff_ports(self, ports_init, ports_end):
        """
        Find allocated pts ports
        """
        diff = list(set(ports_end) - set(ports_init))
        return diff