import argparse
import os
import sys
import yaml
import shutil
import subprocess
import logger
import subprocess
import psutil

cur_dir = os.path.dirname(os.path.abspath(__file__))

class test_framework:
    def __init__(self, wkrdir):
        self.tests_srcs = os.path.abspath(os.path.join(cur_dir, "../src/tests"))
        self.bao_tests_dir = os.path.abspath(os.path.join(cur_dir, "../../bao-tests"))
        self.bao_hypervisor_dir = os.path.abspath(os.path.join(cur_dir, "../../../"))

    def build_guests(self, platform):

        for guest in self.test_config['guests']:
            print("[INFO] Building guest:", guest)

            guest_class = dict_guests.get(guest)
            list_tests = self.test_config['guests'][guest].get('list_tests', "")
            list_suites = self.test_config['guests'][guest].get('list_suites', "")

            # get absolute path of current directory
            cur_dir = os.getcwd()
            tests_srcs_dir = os.path.realpath(
                os.path.join(cur_dir, self.tests_srcs)
            )

            bao_tests_dir = os.path.realpath(
                os.path.join(cur_dir, self.bao_tests_dir)
            )
            guest_instance = guest_class(
                wrkdir, list_tests, list_suites,
                tests_srcs=tests_srcs_dir,
                bao_tests_path=bao_tests_dir
            )

            guest_instance.build(
                platform=self.test_config['platform'],
                arch=platform.architecture,
                toolchain=platform.toolchain,
                irq_flags=interrupt_flags
                )

    def run_cmd(self, cmd, cwd=None):
        print(f"[CMD] {' '.join(cmd)}")
        p = subprocess.run(cmd, cwd=cwd)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    
    def build_hypervisor(self, wrkdir, bao_config_path, platform, irq_flags):
        # Resolve paths
        bao_srcs_path = os.path.abspath(self.bao_hypervisor_dir)
        wrkdir_abs = os.path.abspath(wrkdir)

        # Create an $out-like directory inside bao_hypervisor_dir
        out_dir = os.path.join(bao_srcs_path, "bao_imgs")

        print("[INFO] Setting up Bao hypervisor build environment...")
        print("[INFO]    bao_srcs_path :", bao_srcs_path)
        print("[INFO]    wrkdir_abs    :", wrkdir_abs)
        print("[INFO]    out_dir       :", out_dir)

        guests_build_dir = os.path.join(wrkdir_abs, "guests", "build")
        platform_name = self.test_config['platform']

        env = os.environ.copy()
        env["ARCH"] = platform.architecture
        env["CROSS_COMPILE"] = f"{platform.toolchain}-"

        make_cmd = [
            "make",
            f"PLATFORM={platform_name}",
            f"CONFIG_REPO={bao_config_path}",
            f"CONFIG={platform_name}",
            f"CPPFLAGS=-DBAO_WRKDIR_IMGS={guests_build_dir}"
        ]

        if platform.architecture == "aarch64" and irq_flags:
            gic_version = irq_flags.get("GIC_version", "GICV2")
            make_cmd.append(f"GIC_VERSION={gic_version}")

        print("[CMD] " + " ".join(make_cmd))

        # Run make in the hypervisor source dir (../../../)
        self.run_cmd(make_cmd, cwd=bao_srcs_path)

        bao_bin_path = os.path.join(
            bao_srcs_path, "bin", platform_name, platform_name, "bao.bin"
        )

        print(f"[INFO] Built Bao hypervisor stored at {bao_bin_path}")
        return bao_bin_path

    def clean_build_artifacts(self):
        #ToDo: implement build artifact cleanup process
        pass

    def parse_args(self):
        """
        Parse python script arguments.
        """
        parser = argparse.ArgumentParser(description="Bao Testing Framework")

        parser.add_argument("-log_level", "--log_level",
                    help="Allows to define the amount of information produced"
                         "by the framework: "
                         "0 - only logs the final report, "
                         "1 - logs failed tests and the final report, "
                         "2 - logs all test results and the final report",
                    default=0)

        parser.add_argument("-echo", "--echo",
                    help="Allows to define the filtering of the framework: "
                         "full - does not filter any information"
                         "tf - filters logging not produced by the framework"
                         "none - filter every logging",
                    default="tf")

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
        
        parser.add_argument("-test", "--test",
                    help="Name of default test to be executed",
                    default=" ")
        
        parser.add_argument("-setup", "--setup",
                    help="Target setup (e.g., baremetal freertos)",
                    default=" ")
        
        # either "config" or "test" and "setup" must be provided
        args = parser.parse_args()
        
        test_config = {}
        # if all fields of gicv, irqc, ipic were not provided, return error
        if args.gicv == "" and args.irqc == "" and args.ipic == "":
            parser.error("At least one of --gicv, --irqc or --ipic must be provided when using --test and --setup.")

        if args.gicv != "":
            irq_flags = {'GIC_version': args.gicv}
        else:
            if args.irqc != "":
                irq_flags = {'IRQ_controller': args.irqc}
            if args.ipic != "":
                irq_flags = {'IPIC': args.ipic}

        config_file = os.path.abspath(os.path.join(cur_dir, "test_config.yaml"))
        with(open(config_file, "r")) as f:
            test_config = yaml.safe_load(f)

        list_tests = test_config.get(args.test, [{}])[0].get("list_tests", "")
        list_suites = test_config.get(args.test, [{}])[1].get("list_suites", "")

        guests = {
            args.setup : {
                'list_tests': list_tests,
                'list_suites': list_suites
            }
        }

        self.test_config = {
            'log_level': int(args.log_level),
            'echo': args.echo,
            'platform': args.platform,
            'irq_flags': irq_flags,
            'guests': guests,
            'bao_config': os.path.abspath(os.path.join(cur_dir, f"tests_configurations/setups/{args.setup}")),
            'setup': args.setup
        }


    def launch_test(self, bao_bin, irq_flags, setup, echo):
        logger_inst = logger.TestLogger()

        proc, stderr_path, errf, serial_ports = platform.launch_test(
            bao_bin, irq_flags, setup
        )

        logger_inst.connect_to_platform_port(serial_ports, echo)

        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
                child.wait()
            except psutil.NoSuchProcess:
                pass
        try:
            parent.terminate()
            parent.wait()
        except psutil.NoSuchProcess:
            pass


sys.path.append(os.path.abspath(os.path.join(cur_dir, "platforms")))
from qemu_aarch64_virt import qemu_aarch64_virt

sys.path.append(os.path.abspath(os.path.join(cur_dir, "guests")))
from baremetal import baremetal

dict_platforms = {
    "qemu-aarch64-virt": qemu_aarch64_virt,
    # "qemu-riscv64-virt": qemu_riscv64_virt
}

dict_guests = {
    "baremetal" : baremetal,
}

# main
if __name__ == "__main__":
    wrkdir = os.getcwd()
    wrkdir += "/wrkdir"
    if not os.path.exists(wrkdir):
        os.makedirs(wrkdir)

    tf = test_framework(wrkdir)
    tf.parse_args()

    interrupt_flags = tf.test_config['irq_flags']
    bao_cfg_path_abs = os.path.abspath(tf.test_config['bao_config'])

    platform_class = dict_platforms.get(tf.test_config['platform'])
    platform = platform_class(wrkdir)
    platform.setup_platform()
    platform.build_firmware(interrupt_flags)

    tf.build_guests(platform)
    bao_bin = tf.build_hypervisor(
        wrkdir,
        bao_cfg_path_abs,
        platform,
        interrupt_flags
    )

    tf.launch_test(bao_bin, interrupt_flags, tf.test_config['setup'], tf.test_config['echo'])
