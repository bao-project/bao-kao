"""
Copyright (c) Bao Project and Contributors. All rights reserved
SPDX-License-Identifier: Apache-2.0
Constants to be configured
"""
# Text coloring
RED_TEXT = '\033[31m'
GREEN_TEXT = '\033[32m'
BLUE_TEXT = '\033[34m'
RESET_COLOR = '\033[0m'

# UART concifgs
UART_BAUDRATE = 115200
UART_TIMEOUT = 1
TEST_RESULTS = ''

LOG_LEVEL = 1


def set_log_level(level):
    """Set how much the framework itself reports (see the -l option)."""
    global LOG_LEVEL  # pylint: disable=global-statement
    LOG_LEVEL = int(level)


def print_log(log_type, message, tab_level=0):
    """Print a colorized framework log message.

    Warnings and errors always show. Progress messages show at level 1 when
    they are top level and at level 2 in full; level 0 keeps only the test
    results.
    """
    if log_type not in ("WARNING", "ERROR"):
        if LOG_LEVEL < 1 or (LOG_LEVEL < 2 and tab_level > 0):
            return
    tabs = "  " * tab_level
    # add an arow to indicate the log level
    tabs += "-> " if tab_level > 0 else ""
    dict_colors = {
        "INFO": "\033[94m",
        "ERROR": "\033[91m",
        "WARNING": "\033[93m",
        "SUCCESS": "\033[92m",
        "ENDC": "\033[0m",
    }

    color = dict_colors.get(log_type, "")
    endc = dict_colors["ENDC"]
    print(f"{color}{tabs}[{log_type}] {message}{endc}")
