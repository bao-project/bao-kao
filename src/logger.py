"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
UART utils submodule.
"""

import os
import subprocess
import sys
import threading
import time

import serial

try:
    from prettytable import PrettyTable as PRETTY_TABLE_CLASS  # pylint: disable=import-error
except ModuleNotFoundError:
    PRETTY_TABLE_CLASS = None

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(CUR_DIR, "platforms")))
from generic_platform import FvpTerminalPort  # pylint: disable=import-error,wrong-import-position


class TestLogger:  # pylint: disable=too-many-instance-attributes
    """Read platform logs and parse test/benchmark results."""

    def __init__(self, cpu_freq, timer_freq, benchmark_name=None):
        self.test_tags = {
            "c": "[TESTF-C]",
            "py": "[TESTF-PY]",
            "start": "[TESTF-C] START",
            "end": "[TESTF-C] END",
            "success": "[TESTF-C] SUCCESS",
            "failure": "[TESTF-C] FAILURE",
            "exit": "[TESTF-C] EXIT",
            "boot_failure": "Synchronous Abort",
        }
        self.logger_commands = {
            f"{self.test_tags['c']} SEND_CHAR": self.send_char,
            f"{self.test_tags['c']} SET_TIMEOUT": self.set_timeout,
            f"{self.test_tags['c']} CLEAR_TIMEOUT": self.clear_timeout,
        }
        self.log_level = {
            "full": self.echo_log_full,
            "tf": self.echo_log_tf,
            "none": self.echo_log_none,
            "benchmark": self.echo_log_benchmark,
        }

        self.serial_port = ""
        self.list_events = {
            "event_thread_finished": threading.Event(),
            "event_stop_listener": threading.Event(),
            "event_completed_test": threading.Event(),
        }
        self.test_results = ""
        self.cpu_freq = cpu_freq
        self.timer_freq = timer_freq
        self.benchmark_name = benchmark_name

    @staticmethod
    def print_message(message, message_type="info"):
        """Print a colorized logger message."""
        dict_message_colors = {
            "info": "\033[34m",  # Blue
            "success": "\033[32m",  # Green
            "error": "\033[31m",  # Red
            "warning": "\033[33m",  # Yellow
            "reset": "\033[0m",  # Reset
        }

        message_color = dict_message_colors.get(message_type)
        print(message_color + message + dict_message_colors["reset"])

    def send_char(self, command):
        """Send a character to the serial port."""
        command = command.split()
        if len(command) < 3:
            self.serial_port.write(b"1\r\n")
        else:
            self.serial_port.write(command[2].encode("utf-8") + b"\r\n")

    def set_timeout(self, command):
        """Create timeout thread to stop listener when test stalls."""
        self.list_events["event_completed_test"].clear()
        command = command.split()
        if len(command) < 3:
            return

        timeout = int(command[2])
        self.list_events["event_thread_finished"].clear()

        def timeout_thread(time_left):
            while time_left > 0:
                if self.list_events["event_completed_test"].is_set():
                    return
                time.sleep(1)
                time_left -= 1

            self.list_events["event_stop_listener"].set()
            self.print_message("Timeout reached", "error")

        threading.Thread(target=timeout_thread, args=[timeout]).start()

    def clear_timeout(self, _=None):
        """Cancel active timeout."""
        self.list_events["event_completed_test"].set()

    def echo_log_full(self, serial_results):
        """Print each serial line."""
        for line in serial_results:
            print(line, end="")
        self.list_events["event_thread_finished"].set()

    def echo_log_tf(self, serial_results):
        """Print only the Bao Kao Framework section of the serial output."""
        is_kao_section = False
        for line in serial_results:
            if self.test_tags["start"] in line:
                print(
                    "\n"
                    + "========================================="
                    + "=========================================\n"
                    + "                            Bao Kao Framework\n"
                    + "                                 RESULTS\n"
                    + "========================================="
                    + "========================================="
                    + "\n"
                )
                is_kao_section = True

            elif self.test_tags["end"] in line:
                is_kao_section = False
                print(line, end="")

            if is_kao_section:
                print(line, end="")

        self.list_events["event_thread_finished"].set()

    def echo_log_benchmark(self, serial_results):
        """Print benchmark summary table from serial samples."""
        if self.list_events["event_thread_finished"].is_set():
            return

        print(
            "\n"
            + "========================================="
            + "=========================================\n"
            + "                            Bao Kao Framework\n"
            + "                                 RESULTS\n"
            + "========================================="
            + "========================================="
            + "\n"
        )

        result_tag = "[SAMPLE]"

        def _extract_samples(lines):
            values = []
            for line in lines:
                if result_tag in line:
                    try:
                        values.append(float(line.split(result_tag)[-1].strip()))
                    except ValueError:
                        pass
            return values

        def _extract_ctx_switch_values(lines):
            values = []
            for line in lines:
                stripped = line.strip()
                if not stripped.startswith("Ctx switch:"):
                    continue
                _, raw_value = stripped.split(":", 1)
                raw_value = raw_value.strip()
                try:
                    values.append(float(raw_value))
                except ValueError:
                    pass
            return values

        def _stats(values):
            if not values:
                return None
            n_values = len(values)
            avg_value = sum(values) / n_values
            max_value = max(values)
            min_value = min(values)
            variance = sum((value - avg_value) ** 2 for value in values) / n_values
            std_dev = variance**0.5
            return {
                "count": n_values,
                "average": avg_value,
                "std_dev": std_dev,
                "max": max_value,
                "min": min_value,
            }

        def _format_value(value):
            if float(value).is_integer():
                return str(int(value))
            return f"{value:.3f}"

        def _print_table(values):
            summary = _stats(values)
            if summary is None:
                print("No benchmark numeric results found.")
                return

            benchmark_label = self.benchmark_name if self.benchmark_name else "benchmark"
            if PRETTY_TABLE_CLASS is None:
                print(f"Benchmark: {benchmark_label}")
                print(f"N: {summary['count']}")
                print(f"Average: {_format_value(summary['average'])}")
                print(f"Std Dev: {_format_value(summary['std_dev'])}")
                print(f"Max: {_format_value(summary['max'])}")
                print(f"Min: {_format_value(summary['min'])}")
                return

            table = PRETTY_TABLE_CLASS()
            table.title = "Benchmark summary"
            table.field_names = ["Benchmark", "N", "Average", "Std Dev", "Max", "Min"]
            table.add_row(
                [
                    benchmark_label,
                    summary["count"],
                    _format_value(summary["average"]),
                    _format_value(summary["std_dev"]),
                    _format_value(summary["max"]),
                    _format_value(summary["min"]),
                ]
            )

            print(table)

        sample_values = _extract_samples(serial_results)
        values = sample_values if sample_values else _extract_ctx_switch_values(serial_results)
        _print_table(values)
        self.list_events["event_thread_finished"].set()

    def echo_log_none(self, _serial_results=None):
        """Ignore serial output."""
        self.list_events["event_thread_finished"].set()

    def connect_to_platform_port(self, ports_list, echo, is_benchmark=False):
        """Connect to each serial port and start one listener thread per port."""
        threads = []

        for port in ports_list:
            ser = self.open_connection(port)
            listener_thread = threading.Thread(
                target=self.listener,
                args=(ser, echo, is_benchmark),
            )
            threads.append(listener_thread)

        for thread in threads:
            thread.start()

        return threads

    def wait_for_finish(self, threads):
        """Wait for one listener to complete and then stop all listeners."""
        self.list_events["event_thread_finished"].wait()
        self.list_events["event_stop_listener"].set()

        for thread in threads:
            thread.join()

    def listener(
        self,
        ser_port,
        echo,
        is_benchmark=False,
    ):  # pylint: disable=too-many-branches,too-many-statements
        """Read platform serial stream and dispatch parser/actions."""
        self.serial_port = ser_port

        def decode_and_replace(res):
            replacements = [
                ("\r\n", "\n"),
                ("\x1b[0m\x1b[1;", "\x1b[1;"),
                ("\x1b[1;", "\033["),
                ("\x1b", "\033"),
                ("#$#", "#"),
            ]
            line = res.decode(errors="ignore")
            for old, new in replacements:
                line = line.replace(old, new)
            return line

        def handle_boot_failure(line):
            if self.test_tags["boot_failure"] in line:
                self.print_message(line + " Boot failed.", "error")
                self.test_results = line
                self.clear_timeout()
                self.list_events["event_stop_listener"].set()
                return True
            return False

        def handle_command(line):
            if self.test_tags["c"] in line:
                parts = line.split()
                if len(parts) >= 2:
                    command = parts[0] + " " + parts[1]
                    if command in self.logger_commands:
                        self.logger_commands[command](line)
                    else:
                        self.test_results = line
                        self.clear_timeout()

        def handle_test_completion(res_log, boot_failure, benchmark_mode=False):
            results = {}
            self.clear_timeout()
            if not benchmark_mode and not boot_failure:
                for line in reversed(res_log):
                    if self.test_tags["c"] in line and "END" not in line:
                        for item in line.split():
                            if "#" in item:
                                key, value = item.split("#", 1)
                                results[key] = int(value)
                        self.test_results = results or {"FAIL": 1}
                        break
                else:
                    self.test_results = {"FAIL": 1}

        try:
            while not self.list_events["event_stop_listener"].is_set():
                res_log = []
                boot_failure = False

                while not self.list_events["event_stop_listener"].is_set():
                    try:
                        res = ser_port.readline()
                    except serial.SerialException:
                        self.list_events["event_stop_listener"].set()
                        break

                    if not res:
                        continue

                    new_line = decode_and_replace(res)
                    res_log.append(new_line)

                    if handle_boot_failure(new_line):
                        boot_failure = True

                    handle_command(new_line)

                    if self.test_tags["end"] in new_line:
                        break

                if res_log:
                    handle_test_completion(res_log, boot_failure, is_benchmark)
                    if is_benchmark:
                        if echo == "full":
                            self.echo_log_full(res_log)
                        elif echo == "none":
                            self.echo_log_none(res_log)
                        else:
                            self.echo_log_benchmark(res_log)
                    else:
                        self.log_level[echo](res_log)

        finally:
            try:
                ser_port.close()
            except (serial.SerialException, OSError):
                pass

    @staticmethod
    def open_connection(port, baudrate=115200, uart_timeout_sec=1):
        """Validate and open serial or TCP terminal connections."""
        if isinstance(port, str) and port.startswith("tcp://"):
            addr = port[len("tcp://") :]
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
    """Scan available pseudo-terminal ports."""
    std_out = subprocess.run(["ls", "/dev/pts/"], stdout=subprocess.PIPE, check=True)
    std_out = std_out.stdout.decode("ASCII")
    ports = std_out.split()
    return ports


def diff_ports(ports_init, ports_end):
    """Return newly allocated pseudo-terminal ports."""
    diff = list(set(ports_end) - set(ports_init))
    return diff
