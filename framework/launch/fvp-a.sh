#!/usr/bin/env bash

# Usage check: only 3 arguments expected
if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <bl1_path> <fip_path> <bao-bin-path> [gic_version] [guest_OS]"
  exit 1
fi

bl1_bin="$1"
fip_bin="$2"
bao_bin="$3"
gic_version="${4:-3}"
guest_OS="${5:-baremetal}"

# Set the FVP model path
FVP_MODEL_DIR="./FVP_Model_A"
FVP_MODEL_PATH=$(find "$FVP_MODEL_DIR" -type f -name FVP_Base_RevC-2xAEMvA 2>/dev/null | head -n 1)


# Verify the FVP executable exists
if [ -z "$FVP_MODEL_PATH" ] || [ ! -x "$FVP_MODEL_PATH" ]; then
  echo "FVP BaseA model not found, downloading to $FVP_MODEL_DIR ..."
  mkdir -p "$FVP_MODEL_DIR"
  curl -L https://developer.arm.com/-/media/Files/downloads/ecosystem-models/FVP_Base_RevC-2xAEMvA_11.21_15_Linux64.tgz \
    | tar xz -C "$FVP_MODEL_DIR"

  FVP_MODEL_PATH=$(find "$FVP_MODEL_DIR" -type f -name FVP_Base_RevC-2xAEMvA 2>/dev/null | head -n 1)
  if [ -z "$FVP_MODEL_PATH" ] || [ ! -x "$FVP_MODEL_PATH" ]; then
    echo "Error extracting FVP model (could not find FVP_Base_RevC-2xAEMvA binary)"
    exit 2
  fi
fi

# Check port 5555
if netstat -tuln | grep ":5555 " &>/dev/null; then
  echo "Port 5555 is already in use"
  exit 1
fi

# Create bidirectional PTY for UART0
UART_LINK="./tmp/fvp-uart0"
rm -f "$UART_LINK"
echo "Creating bidirectional UART PTY at $UART_LINK ..."
socat -d -d PTY,raw,echo=0,link=$UART_LINK PTY,raw,echo=0 &
SOCAT_PID=$!
sleep 1
UART_PTS=$(readlink -f "$UART_LINK")
echo "   UART0 PTY available at $UART_PTS"
echo "   You can connect manually via: screen $UART_PTS 115200"

# Launch the FVP model
echo "Launching FVP model from: $FVP_MODEL_PATH"
"$FVP_MODEL_PATH" \
  -C cluster0.supports_multi_threading=0 \
  -C cluster0.mpidr_layout=0 \
  -C cluster1.NUM_CORES=0 \
  -C pctl.startup=0.0.0.0 \
  -C pctl.Affinity-shifted=0 \
  -C pctl.CPU-affinities='0.0.0.0,0.0.0.1,0.0.0.2,0.0.0.3' \
  -C gic_distributor.CPU-affinities='0.0.0.0,0.0.0.1,0.0.0.2,0.0.0.3' \
  -C gic_distributor.reg-base-per-redistributor='0.0.0.0=0x2f100000,0.0.0.1=0x2f120000,0.0.0.2=0x2f140000,0.0.0.3=0x2f160000' \
  -C bp.smsc_91c111.enabled=true \
  -C bp.hostbridge.userNetworking=true \
  -C bp.hostbridge.userNetSubnet=192.168.42.0/24 \
  -C bp.hostbridge.userNetPorts=127.0.0.1:5555=22 \
  -C bp.pl011_uart0.out_file="$UART_PTS" \
  --data="$bl1_bin@0x0" \
  --data="$fip_bin@0x08000000" \
  --data="$bao_bin@0x90000000"

# Cleanup socat after FVP exits
kill "$SOCAT_PID" 2>/dev/null || true
echo "   FVP exited. Socat cleaned up."
