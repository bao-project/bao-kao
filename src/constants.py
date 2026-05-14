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

def print_log(log_type, message, tab_level=0):
    """Print a colorized framework log message."""
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
