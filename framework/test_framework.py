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

def run_command_in_terminal(command):
    """
    Run a command in a new Terminal window.

    Args:
        command (str): The command to execute.
    """
    # pylint: disable=R1732
    terminal_process = subprocess.Popen(
        ['/bin/bash', '-c', command],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
    )
    # pylint: enable=R1732

    return terminal_process

def terminate_children_processes(parent_process):
    """
    Terminate all child processes of the given parent process.

    Args:
        parent_process: The parent process whose children will be terminated.
    """
    parent = psutil.Process(parent_process.pid)
    children = parent.children(recursive=True)
    for child in children:
        child.terminate()
        child.wait()

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

def deploy_test(platform, gicv):
    """
    Deploy a test on a specific platform.

    Args:
        platform (str): The platform to deploy the test on.
    """
    if platform in ["qemu-aarch64-virt"]:
        arch = platform.split("-")[1]
        bao_bin_path = get_file_path("bao.bin")
        flash_bin_path = get_file_path("flash.bin")
        gic_version = gicv.split("GICV")[1]

        run_cmd = "./launch/qemu-aarch64-virt.sh"
        run_cmd += " " + arch
        run_cmd += " " + flash_bin_path
        run_cmd += " " + bao_bin_path
        run_cmd += " " + str(gic_version)

    elif platform in ["qemu-riscv64-virt"]:
        arch = platform.split("-")[1]
        bao_bin_path = get_file_path("bao.bin")
        opensbi_elf_path = get_file_path("opensbi.elf")
        run_cmd = "./launch/qemu-riscv64-virt.sh"
        run_cmd += " " + arch
        run_cmd += " " + opensbi_elf_path
        run_cmd += " " + bao_bin_path

    logger = connection.TestLogger()

    # Get the ports opened before running QEMU
    initial_pts_ports = connection.scan_pts_ports()

    # Launch QEMU
    process = run_command_in_terminal(run_cmd)

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

    print(cons.BLUE_TEXT + "Framework init..." + cons.RESET_COLOR)
    print(cons.BLUE_TEXT +
          "Framework init..." +
          cons.RESET_COLOR)

    args = parse_args()

    if args.clean:
        print(cons.BLUE_TEXT +
            "Cleaning output directory..." +
            cons.RESET_COLOR)

        clean_output()

        print(cons.GREEN_TEXT +
            "Output directory clean!" +
            cons.RESET_COLOR)
        sys.exit(-1)


    print(cons.BLUE_TEXT + "Running nix build..." + cons.RESET_COLOR)

    if args.platform is None:
        print(cons.RED_TEXT +
        "Error: Please provide a --platform." +
        cons.RESET_COLOR)
    else:
        platfrm = args.platform

    if args.recipe is None:
        print(cons.RED_TEXT +
        "Error: Please provide the --recipe argument." +
        cons.RESET_COLOR)
    else:
        recipe = args.recipe
        print("Recipe .nix file: " + recipe)

    BUILD_CMD = 'nix-build ' + recipe
    BUILD_CMD += " --argstr platform " + platfrm
    BUILD_CMD += " --argstr log_level " + str(args.log_level)

    if args.gicv:
        BUILD_CMD += " --argstr GIC_VERSION " + args.gicv
    if args.irqc:
        BUILD_CMD += " --argstr IRQC " + args.irqc
    if args.ipic:
        BUILD_CMD += " --argstr IPIC " + args.ipic

    print("Building with command: " + BUILD_CMD)
    res = os.system(BUILD_CMD)
    if res==0:
        print(cons.GREEN_TEXT +
            "nix build successfully completed..." +
            cons.RESET_COLOR)

    else:
        print(cons.RED_TEXT +
               "nix build failed..." +
               cons.RESET_COLOR)
        sys.exit(-1)

    move_results_to_output()

    print("Interrupt Controller: " + args.gicv)
    print(cons.BLUE_TEXT + "Launching QEMU..." + cons.RESET_COLOR)
    deploy_test(platfrm, args.gicv)
