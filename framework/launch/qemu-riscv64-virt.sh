#!/usr/bin/env nix-shell
#!nix-shell -i bash -p 'with import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/0c924ec948073580a3c3d438746388d05a38028b.zip") {}; qemu_full'

# Check if the correct number of arguments is provided
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <opensbi_elf_path> <bao-bin-path> <guest_OS>"
    exit 1
fi

opensbi_elf_path="$1"
bao_bin_path="$2"
guest_OS="$3"

# Check if port 5555 is already in use
if netstat -tuln | grep ":5555 " &>/dev/null; then
    echo "Port 5555 is already in use"
    exit -1
fi

echo "Guest OS: $guest_OS"
qemu_stderr=$(mktemp)

# Set extra serial arguments based on the guest OS
if [[ "$guest_OS" == "linux" ]]; then
    extra_serial_args="-device virtio-serial-device -chardev pty,id=serial3 -device virtconsole,chardev=serial3"
else
    extra_serial_args="-serial pty"
fi

# Run QEMU
qemu-system-riscv64 -nographic \
    -M virt -cpu rv64 -m 4G -smp 4 \
    -bios "$opensbi_elf_path" \
    -device loader,file="$bao_bin_path",addr=0x80200000,force-raw=on \
    -device virtio-net-device,netdev=net0 \
    -netdev user,id=net0,net=192.168.42.0/24,hostfwd=tcp:127.0.0.1:5555-:22 \
    $extra_serial_args \
    2> "$qemu_stderr"

rm "$qemu_stderr"
exit 0

