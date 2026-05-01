"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
UART utils submodule
"""
import subprocess
import threading
import time
import serial
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(cur_dir, "platforms")))
from generic_platform import FvpTerminalPort



class TestLogger:
    """
    Test logger class
    """
    def __init__(self, cpu_freq, timer_freq):
        self.test_tags = {
            'c':            "[TESTF-C]",
            'py':           "[TESTF-PY]",
            'start':        "[TESTF-C] START",
            'end':          "[TESTF-C] END",
            'success':      "[TESTF-C] SUCCESS",
            'failure':      "[TESTF-C] FAILURE",
            'exit':         "[TESTF-C] EXIT",
            'boot_failure': "Synchronous Abort"
        }
        self.logger_commands = {
            f"{self.test_tags['c']} SEND_CHAR" : self.send_char,
            f"{self.test_tags['c']} SET_TIMEOUT" : self.set_timeout,
            f"{self.test_tags['c']} CLEAR_TIMEOUT" : self.clear_timeout,
        }
        self.log_level = {
            'full'  : self.echo_log_full,
            'tf'    : self.echo_log_tf,
            'none'  : self.echo_log_none,
            'benchmark' : self.echo_log_benchmark
        }

        self.serial_port = ""
        self.list_events = {
            'event_thread_finished': threading.Event(),
            'event_stop_listener': threading.Event(),
            'event_completed_test': threading.Event()
        }
        self.TEST_RESULTS = ''
        self.cpu_freq = cpu_freq
        self.timer_freq = timer_freq

    def print_message(self, message, message_type="info"):
        """
        Print message based on type
        """

        dict_message_colors = {
            "info":     '\033[34m', # Blue
            "success":  '\033[32m', # Green
            "error":    '\033[31m', # Red
            "warning":  '\033[33m', # Yellow
            "reset":    '\033[0m'   # Reset
        }

        message_color = dict_message_colors.get(message_type)
        print(message_color + message + dict_message_colors["reset"])

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
                time.sleep(1)
                timeout -= 1

            self.list_events['event_stop_listener'].set()
            self.print_message("Timeout reached", "error")

        threading.Thread(target=timeout_thread, args=[timeout]).start()

    def clear_timeout(self, _=None):
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
                print(
                    "\n" +
                    "=========================================" +
                    "=========================================\n" +
                    "                            Bao Test Framework\n" +
                    "                                 RESULTS\n" +
                    "=========================================" +
                    "=========================================" +
                    "\n"
                )
                is_tf_section = True

            elif self.test_tags['end'] in line:
                is_tf_section = False
                print(line, end="")

            if is_tf_section:
                print(line, end="")

        self.list_events['event_thread_finished'].set()

    def echo_log_benchmark(self, serial_results):

        if self.list_events['event_thread_finished'].is_set():
            return

        print(
            "\n" +
            "=========================================" +
            "=========================================\n" +
            "                            Bao Test Framework\n" +
            "                                 RESULTS\n" +
            "=========================================" +
            "=========================================" +
            "\n"
        )

        RESULT_TAG = "[SAMPLE]"


        def _parse_samples(lines, result_tag=RESULT_TAG):
            results = []
            for line in lines:
                if result_tag in line:
                    try:
                        results.append(int(line.split(result_tag)[-1].strip()))
                    except ValueError:
                        pass
            return results

        def _stats(xs):
            if not xs:
                return None
            n = len(xs)
            avg = sum(xs) / n
            mx = max(xs)
            mn = min(xs)
            var = sum((x - avg) ** 2 for x in xs) / n  # population variance
            std = var ** 0.5
            return {"n": n, "avg": avg, "max": mx, "min": mn, "std": std, "var": var}

        def _cycles_to_us(cycles):
            if self.timer_freq <= 0:
                return float("nan")
            return (cycles / self.timer_freq) * 1e6

        def _time_unit_and_scale(avg_cycles):
            avg_us = _cycles_to_us(avg_cycles)
            if avg_us < 1:
                return "ns", 1e3
            return "us", 1.0

        def _print_table(xs):
            from prettytable import PrettyTable

            s = _stats(xs)
            if s is None:
                print("No [SAMPLE] results found.")
                return

            table = PrettyTable()
            table.title = f"Benchmark summary (n={s['n']} / CPU freq={self.cpu_freq} Hz)"
            table.field_names = ["Metric", "Average", "Max", "Min", "Std Dev", "Variance"]

            table.add_row([
                "Clock cycles",
                f"{s['avg']:.3f}", f"{s['max']:.3f}", f"{s['min']:.3f}", f"{s['std']:.3f}", f"{s['var']:.3f}",
            ])

            time_unit, scale = _time_unit_and_scale(s["avg"])
            avg_time = _cycles_to_us(s["avg"]) * scale
            max_time = _cycles_to_us(s["max"]) * scale
            min_time = _cycles_to_us(s["min"]) * scale
            std_time = _cycles_to_us(s["std"]) * scale

            if self.cpu_freq <= 0:
                var_time2 = float("nan")
            else:
                var_time2 = s["var"] / (self.cpu_freq ** 2) * 1e12 * (scale ** 2)

            table.add_row([
                f"Execution time ({time_unit})",
                f"{avg_time:.3f}", f"{max_time:.3f}", f"{min_time:.3f}",
                f"{std_time:.3f}", f"{var_time2:.3f}",
            ])

            print(table)

        _print_table(_parse_samples(serial_results))
        self.list_events['event_thread_finished'].set()


    def echo_log_none(self):
        """
        Do not print any serial results.
        """
        self.list_events['event_thread_finished'].set()

    def connect_to_platform_port(self, ports_list, echo, is_benchmark=False):
        """
        Establishes connections to multiple serial ports concurrently and starts a
        listener thread for each port.

        Args:
            ports_list (list): A list of serial port names (e.g., ['COM1',
            '/dev/ttyUSB0']).
        """

        threads = []

        for port in ports_list:
            ser = self.open_connection(port)
            t = threading.Thread(target=self.listener, args=(ser, echo, is_benchmark))
            threads.append(t)

        for thread in threads:
            thread.start()

        return threads

    def wait_for_finish(self, threads):
        self.list_events['event_thread_finished'].wait()
        self.list_events['event_stop_listener'].set()

        for thread in threads:
            thread.join()

    def listener(self, ser_port, echo, is_benchmark=False):
        self.serial_port = ser_port

        def decode_and_replace(res):
            replacements = [
                ('\r\n', '\n'),
                ('\x1b[0m\x1b[1;', '\x1b[1;'),
                ('\x1b[1;', '\033['),
                ('\x1b', '\033'),
                ('#$#', '#'),
            ]
            line = res.decode(errors='ignore')
            for old, new in replacements:
                line = line.replace(old, new)
            return line

        def handle_boot_failure(line):
            if self.test_tags['boot_failure'] in line:
                self.print_message(line + " Boot failed.", "error")
                self.TEST_RESULTS = line
                self.clear_timeout()
                self.list_events['event_stop_listener'].set()
                return True
            return False

        def handle_command(line):
            if self.test_tags['c'] in line:
                parts = line.split()
                if len(parts) >= 2:
                    command = parts[0] + " " + parts[1]
                    if command in self.logger_commands:
                        self.logger_commands[command](line)
                    else:
                        self.TEST_RESULTS = line
                        self.clear_timeout()

        def handle_test_completion(res_log, boot_failure, is_benchmark=False):
            results = {}
            self.clear_timeout()
            if not is_benchmark and not boot_failure:
                for line in reversed(res_log):
                    if self.test_tags['c'] in line and "END" not in line:
                        for item in line.split():
                            if '#' in item:
                                key, value = item.split('#', 1)
                                results[key] = int(value)
                        self.TEST_RESULTS = results or {"FAIL": 1}
                        break
                else:
                    self.TEST_RESULTS = {"FAIL": 1}

        try:
            while not self.list_events['event_stop_listener'].is_set():
                res_log = []
                boot_failure = False

                while not self.list_events['event_stop_listener'].is_set():
                    try:
                        res = ser_port.readline()
                    except serial.SerialException:
                        self.list_events['event_stop_listener'].set()
                        break

                    if not res:
                        continue

                    new_line = decode_and_replace(res)
                    res_log.append(new_line)

                    if handle_boot_failure(new_line):
                        boot_failure = True

                    handle_command(new_line)

                    if self.test_tags['end'] in new_line:
                        break

                if res_log:
                    handle_test_completion(res_log, boot_failure, is_benchmark)
                    self.log_level[echo](res_log)

        finally:
            try:
                ser_port.close()
            except Exception:
                pass

    def open_connection(self, port, baudrate=115200, uart_timeout_sec=1):
        """
        Validate connection between test framework and platform
        """
        if isinstance(port, str) and port.startswith("tcp://"):
            addr = port[len("tcp://"):]
            host, port_num = addr.rsplit(":", 1)

            deadline = time.time() + 15
            last_exc = None

            while time.time() < deadline:
                try:
                    return FvpTerminalPort(host, int(port_num), timeout=uart_timeout_sec)
                except OSError as exc:
                    last_exc = exc
                    time.sleep(0.2)

            raise RuntimeError(f"Failed to connect to {port}: {last_exc}")

        return serial.Serial(str(port), baudrate=baudrate, timeout=uart_timeout_sec)

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