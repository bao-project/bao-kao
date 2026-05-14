"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Generic platform and emulator helpers used by the Bao Kao Framework.
"""

# pylint: disable=duplicate-code
import os
# pylint: disable=duplicate-code
import socket
# pylint: disable=duplicate-code
import subprocess
# pylint: disable=duplicate-code
import sys
# pylint: disable=duplicate-code
import telnetlib

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.abspath(os.path.join(CUR_DIR, "../")) not in sys.path:
    sys.path.append(os.path.abspath(os.path.join(CUR_DIR, "../")))

# pylint: disable=duplicate-code
from constants import print_log  # pylint: disable=wrong-import-position


class FvpTerminalPort:
    """
    Small serial-like wrapper for FVP terminal TCP endpoints.

    Exposes .readline(), .write(), .close(), and .name so the logger can
    treat it like a serial port.
    """

    def __init__(self, host, port, timeout=1):
        """
        Initialize a TCP-backed terminal endpoint.

        Args:
            host (str): Remote host name or IP address.
            port (int): TCP port number.
            timeout (int | float): Read timeout in seconds.
        """
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self.name = f"tcp://{host}:{port}"
        self.telnet_client = telnetlib.Telnet(host, int(port), timeout)

    def readline(self):
        """
        Read one line from the terminal connection.

        Returns:
            bytes: Received line data, or an empty byte string on timeout/EOF.
        """
        try:
            return self.telnet_client.read_until(b"\n", self.timeout)
        except EOFError:
            return b""
        except socket.timeout:
            return b""

    def write(self, data):
        """
        Write raw data to the terminal connection.

        Args:
            data (bytes): Data to send.
        """
        self.telnet_client.write(data)

    def close(self):
        """Close the terminal connection."""
        self.telnet_client.close()


class generic_platform:  # pylint: disable=invalid-name,too-few-public-methods
    """Base platform abstraction shared by real boards and emulators."""

    def __init__(self, wrkdir):  # pylint: disable=unused-argument
        """
        Initialize common platform state.

        Args:
            wrkdir (str): Framework working directory.
        """
        self.is_emulated = False

    @staticmethod
    def run_command(command, log_tab_level=0, cwd=None):
        """
        Launch a subprocess and return the process handle.

        Args:
            command (list[str]): Command and arguments to execute.
            log_tab_level (int): Indentation level for logging output.
            cwd (str | None): Optional working directory.

        Returns:
            subprocess.Popen: Spawned process handle.
        """
        print_log(
            "[INFO]",
            f"Running command: {' '.join(command)}",
            tab_level=log_tab_level,
        )
        proc = subprocess.Popen(  # pylint: disable=consider-using-with
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc


class generic_emulator(generic_platform):  # pylint: disable=invalid-name
    """Base emulator helper with port and pseudo-terminal utilities."""

    def __init__(self, wrkdir):
        """
        Initialize emulator-specific state.

        Args:
            wrkdir (str): Framework working directory.
        """
        super().__init__(wrkdir)
        self.is_emulated = True

    @staticmethod
    def check_port_in_use(host, port):
        """
        Check whether a TCP port is currently in use.

        Args:
            host (str): Host name or IP address.
            port (int): TCP port number.

        Returns:
            bool: True if the port is open, otherwise False.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex((host, port)) == 0

    @staticmethod
    def scan_pts_ports():
        """
        Scan available pseudo-terminal ports.

        Returns:
            list[str]: Available `/dev/pts` entries.
        """
        result = subprocess.run(
            ["ls", "/dev/pts/"],
            stdout=subprocess.PIPE,
            check=True,
        )
        return result.stdout.decode("ascii").split()

    @staticmethod
    def diff_ports(ports_init, ports_end):
        """
        Find pseudo-terminal ports allocated between two snapshots.

        Args:
            ports_init (list[str]): Initial port list.
            ports_end (list[str]): Final port list.

        Returns:
            list[str]: Ports present only in the final snapshot.
        """
        return list(set(ports_end) - set(ports_init))
