#!/usr/bin/env nix-shell
#!nix-shell -i bash -p 'with import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/0c924ec948073580a3c3d438746388d05a38028b.zip") {}; qemu'

# # Check if a version argument is provided
# if [ -z "$4" ]; then
#     echo "Usage: $0 <qemu-platform> <flash_bin_path> <bao-bin-path> <gic_version> <guest_OS>"
#     exit 1
# fi

# qemu_platform="$1"
# flash_bin_path="$2"
# bao_bin_path="$3"
# gic_version="$4"
# guest_OS="$5"

# if netstat -tuln | grep ":5555 " &>/dev/null; then
#     echo "Port 5555 is already in use"
#     exit -1
# fi

# qemu_stderr=$(mktemp)

# if [[ "$guest_OS" == "linux" ]]; then
#   extra_serial_args="-device virtio-serial-device -chardev pty,id=serial3 -device virtconsole,chardev=serial3 -serial pty"
# else
#   extra_serial_args="-serial pty"
# fi

# qemu-system-"$qemu_platform" -nographic \
#     -M virt,secure=on,virtualization=on,gic-version=$gic_version \
#     -cpu cortex-a53 -smp 4 -m 4G \
#     -bios "$flash_bin_path" \
#     -device loader,file="$bao_bin_path",addr=0x50000000,force-raw=on \
#     -device virtio-net-device,netdev=net0 -netdev user,id=net0,hostfwd=tcp:127.0.0.1:5555-:22 \
#     $extra_serial_args \
#     2> "$qemu_stderr"


# rm "$qemu_stderr"
# exit 0


if [ -z "$3" ]; then
    echo "Usage: $0 <flash_bin_path> <bao-bin-path> <gic_version> <guest_OS>"
    exit 1
fi


flash_bin_path="$1"
bao_bin_path="$2"
gic_version="$3"
guest_OS="$4"


if netstat -tuln | grep ":5555 " &>/dev/null; then
    echo "Port 5555 is already in use"
    exit -1
fi


qemu_stderr=$(mktemp)


if [[ "$guest_OS" == "linux" ]]; then
  extra_serial_args="-device virtio-serial-device -chardev pty,id=serial3 -device virtconsole,chardev=serial3 -serial pty"
else
  extra_serial_args="-serial pty"
fi


qemu-system-aarch64 -nographic \
    -M virt,secure=on,virtualization=on,gic-version=$gic_version \
    -cpu cortex-a53 -smp 4 -m 4G \
    -bios "$flash_bin_path" \
    -device loader,file="$bao_bin_path",addr=0x50000000,force-raw=on \
    -device virtio-net-device,netdev=net0 -netdev user,id=net0,hostfwd=tcp:127.0.0.1:5555-:22 \
    $extra_serial_args \
    2> "$qemu_stderr"



rm "$qemu_stderr"
exit 0
