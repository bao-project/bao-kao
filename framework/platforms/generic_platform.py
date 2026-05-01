import socket
import subprocess
import sys
import os
import telnetlib

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "../")))
from constants import print_log


class FvpTerminalPort:
    """
    Small serial-like wrapper for FVP terminal TCP endpoints.
    Exposes .readline(), .write(), .close(), and .name so logger can
    treat it like a serial port.
    """

    def __init__(self, host, port, timeout=1):
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self.name = f"tcp://{host}:{port}"
        self.tn = telnetlib.Telnet(host, int(port), timeout)

    def readline(self):
        try:
            return self.tn.read_until(b"\n", self.timeout)
        except EOFError:
            return b""
        except socket.timeout:
            return b""

    def write(self, data):
        self.tn.write(data)

    def close(self):
        self.tn.close()


class generic_platform:
    def __init__(self, wrkdir):
        # self.name = "generic_platform"
        self.is_emulated = False
    
    def run_command(self, command, log_tab_level=0, cwd=None):
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        print_log("[INFO]", f"Running command: {' '.join(command)}", tab_level=log_tab_level)
        return proc

class generic_emulator(generic_platform):
    def __init__(self, wrkdir):
        # self.name = "emulator"
        self.is_emulated = True

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