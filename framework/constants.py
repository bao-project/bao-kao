# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved

"""
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

# Platform/architecture dictionary
PLAT_ARCH_DICT = {
    "zcu102" : "aarch64",               # Xilinx ZCU102
    "zcu104" : "aarch64",               # Xilinx ZCU104
    "imx8qm" : "aarch64",               # NXP i.MX8QM
    "tx2" : "aarch64",                  # Nvidia TX2
    "rpi4" : "aarch64",		            # Raspberry 4 Model B
    "qemu-aarch64-virt" : "aarch64",	# QEMU Aarch64 virt
    "qemu-riscv64-virt" : "riscv"	    # QEMU RV64 virt
}

PLAT_TOOLCHAIN_DICT = {
    "aarch64" : "aarch64-none-elf",
    "riscv" : "riscv64-uknown-elf"
}

# Directories
MAIN_DIR = '../'

PYTHON_TAG = "[TESTF-PY]"
C_TAG = "[TESTF-C]"
DESC_WIDTH = 60
