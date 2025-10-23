#!/usr/bin/env bash

# Usage: <bao-bin-path> <arch> <vm-image-1> [<vm-image-2> ...]
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <bao-bin-path> <arch> [<vm-image>...]"
    exit 1
fi

bao_bin="$1"
gic_version="$2"
arch="$3"
shift 3
vm_images=("$@")
unset 'vm_images[-1]'  # Remove last empty argument if any

# Set the FVP model path (local workspace)
FVP_MODEL_DIR="./FVP_Model_R"
FVP_MODEL_PATH="$FVP_MODEL_DIR/AEMv8R_base_pkg/models/Linux64_GCC-9.3/FVP_BaseR_AEMv8R"

# Download/extract if not present
if [ ! -x "$FVP_MODEL_PATH" ]; then
    echo "FVP BaseR model not found, downloading to $FVP_MODEL_DIR ..."
    mkdir -p "$FVP_MODEL_DIR"

    curl -L https://developer.arm.com/-/media/Files/downloads/ecosystem-models/FVP_Base_AEMv8R_11.21_15_Linux64.tgz \
        | tar xz -C "$FVP_MODEL_DIR"

    # Dynamically find the extracted FVP binary
    FVP_MODEL_PATH=$(find "$FVP_MODEL_DIR" -type f -name FVP_BaseR_AEMv8R 2>/dev/null | head -n 1)

    if [ -z "$FVP_MODEL_PATH" ] || [ ! -x "$FVP_MODEL_PATH" ]; then
        echo "Error extracting FVP model (FVP_BaseR_AEMv8R binary not found)"
        exit 2
    fi
fi

# Check port 5555
if netstat -tuln | grep ":5555 " &>/dev/null; then
    echo "Port 5555 is already in use"
    exit 1
fi

# Create UART PTY
mkdir -p ./tmp
UART_LINK="./tmp/fvp-uart0"
rm -f "$UART_LINK"
echo "Creating bidirectional UART PTY at $UART_LINK ..."
socat -d -d PTY,raw,echo=0,link=$UART_LINK PTY,raw,echo=0 &
SOCAT_PID=$!
sleep 1
UART_PTS=$(readlink -f "$UART_LINK")
echo "   UART0 PTY available at $UART_PTS"
echo "   You can connect manually via: screen $UART_PTS 115200"

rm "$PTYS_LOG"

# Compose VM image arguments
vm_data_args=""
for img in "${vm_images[@]}"; do
    vm_data_args+=" --data=${img}@0x0"
done

if [[ "$arch" == "aarch64" ]]; then
    has_aarch64=1
    vmsa_supported=1
else
    has_aarch64=0
    vmsa_supported=0
fi

echo "Launching FVP BaseR from: $FVP_MODEL_PATH"
"$FVP_MODEL_PATH" \
  -C gic_distributor.has-two-security-states=0 \
  -C cluster0.gicv3.cpuintf-mmap-access-level=2 \
  -C cluster0.gicv3.SRE-EL2-enable-RAO=1 \
  -C cluster0.has_aarch64=$has_aarch64 \
  -C cluster0.VMSA_supported=$vmsa_supported \
  -C bp.smsc_91c111.enabled=true \
  -C bp.hostbridge.userNetworking=true \
  -C bp.hostbridge.userNetSubnet=192.168.42.0/24 \
  -C bp.hostbridge.userNetPorts=127.0.0.1:5555=22 \
  -C bp.pl011_uart1.uart_enable=1 \
  -C bp.pl011_uart1.out_file="$UART_PTS" \
  --data="$bao_bin@0x0" \
  $vm_data_args

# Cleanup socat after FVP exits
kill "$SOCAT_PID" 2>/dev/null || true
echo "FVP exited. Socat cleaned up."
