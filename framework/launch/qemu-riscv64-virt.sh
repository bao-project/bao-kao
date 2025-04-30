#!/usr/bin/env nix-shell
#!nix-shell --pure -p unixtools.netstat -p qemu -i bash

# Check if a version argument is provided
if [ -z "$3" ]; then
    echo "Usage: $0 <qemu-platform> <opensbi_elf_path> <bao-bin-path> <guest_OS>"
    exit 1
fi

qemu_platform="$1"
opensbi_elf_path="$2"
bao_bin_path="$3"
guest_OS="$4"

if netstat -tuln | grep ":5555 " &>/dev/null; then
    exit -1
fi

if [[ "$guest_OS" == "linux" ]]; then
    extra_serial_args="-device virtio-serial-device -chardev pty,id=serial3 -device virtconsole,chardev=serial3 -serial pty"
else
    extra_serial_args="-serial pty"
fi

qemu-system-"$qemu_platform" -nographic \
    -M virt -cpu rv64 -m 4G -smp 4 \
    -bios "$opensbi_elf_path" \
    -device loader,file="$bao_bin_path",addr=0x80200000,force-raw=on \
    -device virtio-net-device,netdev=net0 \
    -netdev user,id=net0,net=192.168.42.0/24,hostfwd=tcp:127.0.0.1:5555-:22 \
    $extra_serial_args \
    2> "$qemu_stderr"

rm "$qemu_stderr"
exit 0