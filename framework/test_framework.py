# SPDX-License-Identifier: Apache-2.0
# Copyright (c) Bao Project and Contributors. All rights reserved

"""
Test framework main file
"""
import argparse
import os
import shutil
import sys
import subprocess
import psutil
import constants as cons
import connection
import datetime
import shlex
import re
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

test_config = {
    'platform': '',
    'nix_file': '',
    'suites': '',
    'tests': '',
}

def parse_args():
    """
    Parse python script arguments.
    """
    parser = argparse.ArgumentParser(description="Bao Testing Framework")

    parser.add_argument("-bao_test_src_path", "--bao_test_src_path",
                        help="Path to bao-test /src dir",
                        default="../src")

    parser.add_argument("-tests_src_path", "--tests_src_path",
                        help="Path to bao-test /src dir",
                        default="../../src")

    parser.add_argument("-clean", action='store_true',
                    help="Clean output directory")

    parser.add_argument("-echo", "--echo",
                    help="Allows to define the filtering of the framework: "
                         "full - does not filter any information"
                         "tf - filters logging not produced by the framework"
                         "none - filter every logging",
                    default="tf")

    parser.add_argument("-log_level", "--log_level",
                    help="Allows to define the amount of information produced"
                         "by the framework: "
                         "0 - only logs the final report, "
                         "1 - logs failed tests and the final report, "
                         "2 - logs all test results and the final report",
                    default=0)

    parser.add_argument("-recipe", "--recipe",
                    help="Path to the .nix recipe file",
                    default="../../recipes/single-baremetal/default.nix")

    parser.add_argument("-platform", "--platform",
                    help="Used define the target platform",
                    default=" ")

    parser.add_argument("-gicv", "--gicv",
                    required=False,
                    help="Used to define the GIC version setup for the platform",
                    default="")
    parser.add_argument("-irqc", "--irqc",
                    required=False,
                    help="Used to define the IRQ controller setup for the platform",
                    default="")
    parser.add_argument("-ipic", "--ipic",
                    required=False,
                    help="Used to define the IPIC setup for the platform",
                    default="")

    input_args = parser.parse_args()
    return input_args

# def run_command_in_terminal(command):
#     """
#     Run a command in a new Terminal window.

#     Args:
#         command (str): The command to execute.
#     """
#     # pylint: disable=R1732
#     terminal_process = subprocess.Popen(
#         ['/bin/bash', '-c', command],
#         stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
#     )
#     # pylint: enable=R1732

#     return terminal_process

def print_status_message(message, label="status", status=None, exit_on_failure=False):
    """
    Print a status message with optional success/failure formatting and timestamp.

    Args:
        message (str): The message to print.
        label (str): Label to categorize the message.
        status (str or None): Use 'success', 'failure', or None for neutral.
        exit_on_failure (bool): Exit the script if failure.
    """
    now = datetime.now()
    time_str = now.strftime("%H:%M:%S")
    label_fmt = f"[{label.upper():<10}]"

    # Determine formatting
    if status == "success":
        status_fmt = "[SUCCESS]"
        color = cons.GREEN_TEXT
    elif status == "failure":
        status_fmt = "[FAILURE]"
        color = cons.RED_TEXT
    else:
        status_fmt = " " * 9  # Neutral alignment
        color = ""

    desc_fmt = message[:cons.DESC_WIDTH].ljust(cons.DESC_WIDTH)
    print(f"{label_fmt} {color}{status_fmt} {desc_fmt}{cons.RESET_COLOR} ({time_str})")

    if status == "failure" and exit_on_failure:
        sys.exit(-1)

def run_command_in_terminal(command, label="command", verbose="Running command..."):
    """
    Run a command in the background and redirect output to a log file.

    Args:
        command (str): The shell command to run.
        label (str): A label to include in the log filename.
        verbose (str): Description shown before launching.
    """
    now = datetime.now()
    time_str = now.strftime("%H:%M:%S")
    file_timestamp = now.strftime("%Y%m%d_%H%M%S")

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{label}_{file_timestamp}.log")
    log_str = f"[Log: {log_file}]"

    label_fmt = f"[{label.upper():<10}]"
    status_fmt = " " * 9  # Neutral alignment for visual consistency
    desc_fmt = verbose[:cons.DESC_WIDTH].ljust(cons.DESC_WIDTH)

    print(f"{label_fmt} {status_fmt} {desc_fmt} ({time_str}) {log_str}")

    with open(log_file, "w") as log_fp:
        process = subprocess.Popen(
            ['/bin/bash', '-c', command],
            stdout=log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL
        )

    return process


def terminate_children_processes(parent_process):
    """
    Terminate all child processes of the given parent process.

    Args:
        parent_process: The parent process whose children will be terminated.
    """
    parent = psutil.Process(parent_process.pid)
    children = parent.children(recursive=True)
    for child in children:
        try:
            child.terminate()
            child.wait()
        except psutil.NoSuchProcess:
            pass

def get_file_path(filename):
    """
    Search for a file named 'filename' within 'result' directories.
    Args:
    - filename: The name of the file to search for.
    Returns:
    - The path to the file if found, otherwise returns None.
    """
    cur_dir = os.getcwd()
    os.chdir("./output")
    result_directories = [
        d for d in os.listdir() if d.startswith('result') and os.path.isdir(d)
        ]

    for directory in result_directories:
        dir_path = os.path.join(os.getcwd(), directory)
        for root, _, files in os.walk(dir_path):
            if filename in files:
                os.chdir(cur_dir)
                return os.path.join(root, filename)

    print(f"File '{filename}' not found in any 'result' directory.")
    sys.exit(-1)

def extract_vm_regions(config_file_path):
    """
    Returns a flat list of region base addresses (as strings) for all VMs.
    """
    with open(config_file_path) as f:
        content = f.read()

    vm_region_blocks = re.findall(r'\.regions\s*=\s*\(struct vm_mem_region\[\]\)\s*\{([^}]+)\}', content)
    bases = []
    for block in vm_region_blocks:
        bases += [base.split('=')[1].strip() for base in re.findall(r'\.base\s*=\s*0x[0-9A-Fa-f]+', block)]
    return bases

def extract_guest_names(nix_recipe_path):
    """
    Extract 'guest_name' values from the .nix file.
    Returns a list of strings.
    """
    names = []
    with open(nix_recipe_path) as f:
        for line in f:
            match = re.search(r'guest_name\s*=\s*"([^"]+)"', line)
            if match:
                names.append(match.group(1))
    return names

def deploy_test(platform, gicv, guest_os, config_file_path=None, nix_recipe_path=None):
    """
    Deploy a test on a specific platform.

    Args:
        platform (str): The platform to deploy the test on.
    """
    bao_bin_path = get_file_path("bao.bin")
    if platform in ["qemu-aarch64-virt", "fvp-a", "fvp-r"]:
        gic_version = gicv.split("GICV")[1]

        run_cmd = "./launch/" + platform + ".sh"

        if platform == "qemu-aarch64-virt":
            flash_bin_path = get_file_path("flash.bin")
            run_cmd += " " + flash_bin_path
        
        elif platform == "fvp-a":
            fip_bin_path = get_file_path("fip.bin")
            bl1_bin_path = get_file_path("bl1.bin")
            run_cmd += " " + bl1_bin_path
            run_cmd += " " + fip_bin_path

            
            


        run_cmd += " " + bao_bin_path
        run_cmd += " " + str(gic_version)

        if platform == "fvp-r":
            assert config_file_path and nix_recipe_path, "FVP-R requires config and recipe paths."
            vm_regions = extract_vm_regions(config_file_path)
            guest_names = extract_guest_names(nix_recipe_path)

            run_cmd += " aarch64"

            for idx, region_base in enumerate(vm_regions):
                guest_bin_path = get_file_path(guest_names[idx] + ".bin")
                run_cmd += f" {guest_bin_path}@0x{int(region_base, 16):X}"


    elif platform in ["qemu-riscv64-virt"]:
        opensbi_elf_path = get_file_path("opensbi.elf")
        run_cmd = "./launch/qemu-riscv64-virt.sh"
        run_cmd += " " + opensbi_elf_path
        run_cmd += " " + bao_bin_path

    run_cmd += " " + guest_os

    logger = connection.TestLogger()

    # Get the ports opened before running QEMU
    initial_pts_ports = connection.scan_pts_ports()

    # Launch QEMU
    print("Launching platform...", run_cmd)
    process = run_command_in_terminal(
        run_cmd, label="qemu", 
        verbose="Launching QEMU platform...") # run_command_in_terminal(run_cmd)

    # Initially set the end ports as the ports obtained before running QEMU
    final_pts_ports = initial_pts_ports

    # Continuously scan for ports until the ports after running QEMU differ
    # from the initial ports; this retrieves the pts ports opened by QEMU
    while final_pts_ports == initial_pts_ports:
        final_pts_ports = connection.scan_pts_ports()
        if process.poll():
            print(cons.RED_TEXT +
                f"Error launching QEMU (exited with code {process.returncode})" +
                cons.RESET_COLOR)
            sys.exit(-1)
    
    # Find the difference between the initial and final pts ports
    diff_ports = connection.diff_ports(initial_pts_ports, final_pts_ports)

    logger.connect_to_platform_port(diff_ports, args.echo)
    terminate_children_processes(process)

def clean_output():
    """
    Removes the folder './output/' and all its contents.

    This function recursively deletes all files and subdirectories within
    the './output/' folder and finally removes the 'output' directory itself.
    """
    folder_path = './output/'
    try:
        shutil.rmtree(folder_path)
    except FileNotFoundError:
        print(f"Folder '{folder_path}' not found.")
        sys.exit(-1)
    except OSError as err:
        print(f"Error: {folder_path} : {err.strerror}")
        sys.exit(-1)

def move_results_to_output():
    """
    Moves all 'results' folders into the 'output' folder.

    This function searches for folders named 'results' within the current
    directory and moves them into the 'output' folder if it exists. If the
    'output' folder does not exist, it creates the 'output' folder and moves the
    'results' folders into it.
    """
    if os.path.exists('output'):
        clean_output()

    os.makedirs('output')

    count = 1
    while True:
        old_folder = f'{"result" if count == 1 else f"result-{count}"}'

        if not os.path.exists(old_folder):
            break

        new_folder = f'{"result" if count == 1 else f"result-{count}"}'
        shutil.move(old_folder, os.path.join('./output/', new_folder))
        count += 1

if __name__ == '__main__':
    print_status_message("Framework init...", label="init")

    args = parse_args()

    if args.clean:
        print_status_message("Cleaning output directory...", label="cleanup")
        clean_output()
        print_status_message("Output directory clean!", label="cleanup", status="success", exit_on_failure=True)

    print_status_message("Running nix build...", label="nix")

    if args.platform is None:
        print_status_message("Error: Please provide a --platform.", label="args", status="failure", exit_on_failure=True)
    else:
        platfrm = args.platform

    if args.recipe is None:
        print_status_message("Error: Please provide the --recipe argument.", label="args", status="failure", exit_on_failure=True)
    else:
        recipe = args.recipe

    # Construct build command
    BUILD_CMD = f"nix-build {recipe} --argstr platform {platfrm} --argstr log_level {args.log_level}"
    if args.gicv:
        BUILD_CMD += f" --argstr GIC_VERSION {args.gicv}"
    if args.irqc:
        BUILD_CMD += f" --argstr IRQC {args.irqc}"
    if args.ipic:
        BUILD_CMD += f" --argstr IPIC {args.ipic}"

    build_process = run_command_in_terminal(
        BUILD_CMD,
        label="nix_build",
        verbose="Building setup with nix..."
    )

    ret_code = build_process.wait()
    if ret_code == 0:
        print_status_message("nix build successfully completed.", label="nix_build", status="success")
    else:
        print_status_message("nix build failed.", label="nix_build", status="failure", exit_on_failure=True)

    move_results_to_output()

    recipe_name = recipe.split("tests/recipes/")[1].split("/")[0]
    guest_os = recipe_name.split("-")[0]

    recipe_dir = os.path.dirname(recipe)
    config_path = os.path.join(recipe_dir, "configs", platfrm) + ".c"


    deploy_test(platfrm, args.gicv, guest_os, 
                config_file_path=config_path, 
                nix_recipe_path=recipe)
    
    if(cons.TEST_RESULTS.get('FAIL', 0)) > 0:
        sys.exit(0)
    else:
        sys.exit(-1)
