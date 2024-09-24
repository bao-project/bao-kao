"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
UART utils submodule
"""
import subprocess
import threading
import time
import serial
import constants as cons


class TestLogger:
    """
    Test logger class
    """
    def __init__(self):
        self.test_tags = {
            'c': "[TESTF-C]",
            'py': "[TESTF-PY]",
            'start': "[TESTF-C] START",
            'end': "[TESTF-C] END",
            'success': "[TESTF-C] SUCCESS",
            'failure': "[TESTF-C] FAILURE",
            'exit': "[TESTF-C] EXIT"
        }
        self.logger_commands = {
            f"{self.test_tags['c']} SEND_CHAR" : self.send_char,
            f"{self.test_tags['c']} SET_TIMEOUT" : self.set_timeout,
        }
        self.log_level = {
            'full'  : self.echo_log_full,
            'tf'    : self.echo_log_tf,
            'none'  : self.echo_log_none
        }
        # create a list of threading events
        # self.event_thread_finished = threading.Event()
        # self.event_stop_listener = threading.Event()
        self.serial_port = ""
        self.list_events = {
            'event_thread_finished': threading.Event(),
            'event_stop_listener': threading.Event(),
            'event_completed_test': threading.Event()
        }

    def send_char(self, command):
        """"
        Send a character to the serial port
        """
        command = command.split()
        if len(command) < 3:
            self.serial_port.write(b"1\r\n")
        else:
            self.serial_port.write(command[2].encode('utf-8') + b"\r\n")

    def set_timeout(self, command):
        """"
        Create a thread to count x ms before finishing the listener thread
        """
        self.list_events['event_completed_test'].clear()
        command = command.split()
        if len(command) < 3:
            return

        timeout = int(command[2])
        self.list_events['event_thread_finished'].clear()

        def timeout_thread(timeout):
            while timeout > 0:
                if self.list_events['event_completed_test'].is_set():
                    return
                time.sleep(1/1000)
                timeout -= 1

            self.list_events['event_stop_listener'].set()
            print(cons.RED_TEXT +
                "Timeout reached" +
                cons.RESET_COLOR)

        threading.Thread(target=timeout_thread, args=[timeout]).start()

    def unset_timeout(self):
        """
        Cancel the timeout
        """
        self.list_events['event_completed_test'].set()

    def echo_log_full(self, serial_results):
        """
        Print each line in the serial results.

        Args:
            serial_results (list): A list of lines got from serial communication.

        Returns:
            None
        """
        for line in serial_results:
            print(line, end="")
        self.list_events['event_thread_finished'].set()

    def echo_log_tf(self, serial_results):
        """
        Filter and print serial results within the TF section.

        Args:
            serial_results (list): A list of lines got from serial communication.

        Returns:
            None
        """
        is_tf_section = False
        for line in serial_results:
            if self.test_tags['start'] in line:
                is_tf_section = True

            elif self.test_tags['end'] in line:
                is_tf_section = False
                print(line, end="")

            if is_tf_section:
                print(line, end="")

        self.list_events['event_thread_finished'].set()

    def echo_log_none(self):
        """
        Do not print any serial results.
        """
        self.list_events['event_thread_finished'].set()

    def connect_to_platform_port(self, ports_list, echo):
        """
        Establishes connections to multiple serial ports concurrently and starts a
        listener thread for each port.

        Args:
            ports_list (list): A list of serial port names (e.g., ['COM1',
            '/dev/ttyUSB0']).
        """

        threads = []

        for port in ports_list:
            self.open_connection(port)
            new_thread = threading.Thread(target=self.listener, args=[self.serial_port, echo])
            threads.append(new_thread)

        for thread in threads:
            thread.start()

        self.list_events['event_thread_finished'].wait()
        self.list_events['event_stop_listener'].set()

        for thread in threads:
            thread.join()


    def listener(self, ser_port, echo):
        """
        Listener to receive test results
        """
        replacements = [
            ('\\r\\n', '\r\n'),
            ('\\x1b[0m\\x1b[1;', '\\x1b[1;'),
            ('\\x1b[1;', '\033['),
            ('\\x1b', '\033'),
            ('#$#', '#')
        ]

        while not self.list_events['event_stop_listener'].is_set():
            res = b""
            res_log = []

            while not (res.endswith(b"\r\n") and (self.test_tags['end']).encode('utf-8') in res):
                res = ser_port.readline()
                new_line = res.decode(errors='ignore')
                for old, new in replacements:
                    new_line = new_line.replace(old, new)
                res_log.append(new_line)

                if self.test_tags['c'] in new_line:
                    command = new_line.split()[0] + " " + new_line.split()[1]
                    if command in self.logger_commands:
                        self.logger_commands[command](new_line)
                    else:
                        cons.TEST_RESULTS = new_line
                        self.unset_timeout()

                if self.list_events['event_stop_listener'].is_set():
                    break

            for line in reversed(res_log):
                if self.test_tags['c'] in line:
                    cons.TEST_RESULTS = line
                    break

            self.log_level[echo](res_log)

        print(cons.BLUE_TEXT +
            "Closing connection to " +
            ser_port.name +
            "..." +
            cons.RESET_COLOR)

        ser_port.close()


    def open_connection(self, port):
        """
        Validate connection between test framework and platform
        """

        port_name = '/dev/pts/' + str(port)
        ser = serial.Serial(port_name,
                            cons.UART_BAUDRATE,
                            timeout=cons.UART_TIMEOUT
                            )
        print(cons.BLUE_TEXT +
            "Connecting to " +
            port_name +
            "..." +
            cons.RESET_COLOR)

        ser.close()
        ser.open()

        self.serial_port = ser

def scan_pts_ports():
    """
    Scan available pts ports
    """
    std_out = subprocess.run(['ls', '/dev/pts/'],
                            stdout=subprocess.PIPE,
                            check=True)
    std_out = std_out.stdout.decode('ASCII')
    ports = std_out.split()
    return ports

def diff_ports(ports_init, ports_end):
    """
    Find allocated pts ports
    """
    diff = list(set(ports_end) - set(ports_init))
    return diff
