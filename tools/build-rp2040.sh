#!/usr/bin/env bash
set -euo pipefail

# Build MicroPython for RP2040 (Raspberry Pi Pico)
# This script assumes it's run from the repository root inside the container.

ROOT_DIR=$(pwd)
OUT_DIR="$ROOT_DIR/dist"
mkdir -p "$OUT_DIR"

echo "==> Initialising submodules for rp2"
make -C ports/rp2 submodules

echo "==> Fetching ulab submodule"
# Some repos may not have the submodule initialised yet; ignore if already present
if [ ! -d "lib/ulab" ]; then
    git submodule update --init lib/ulab || true
else
    git submodule update --init --recursive lib/ulab || true
fi

echo "==> Building mpy-cross"
make -C mpy-cross -j"$(nproc)"

echo "==> Building rp2 port (Pico/Pico W)"
pushd ports/rp2 >/dev/null
# You can set BOARD=PICO or PICO_W via env var BOARD, default to PICO
: "${BOARD:=PICO}"
make -j"$(nproc)" BOARD="$BOARD" USER_C_MODULES=../../lib/ulab/code/micropython.cmake

# Try common output locations for UF2
UF2_CANDIDATES=(
  "build-${BOARD}/firmware.uf2"
  "build-${BOARD}/micropython.uf2"
  "build-${BOARD}/firmware/micropython.uf2"
)

FOUND_UF2=""
for f in "${UF2_CANDIDATES[@]}"; do
  if [ -f "$f" ]; then
    FOUND_UF2="$f"
    break
  fi
done

if [ -z "$FOUND_UF2" ]; then
  echo "ERROR: Could not find UF2 artifact in expected locations" >&2
  find . -maxdepth 3 -type f -name '*.uf2' -print || true
  exit 1
fi

popd >/dev/null

# Copy artifact to dist with a helpful name
ART_NAME="micropython_${BOARD}_$(date -u +%Y%m%d).uf2"
cp "ports/rp2/${FOUND_UF2}" "${OUT_DIR}/${ART_NAME}"

echo "==> Build finished: ${OUT_DIR}/${ART_NAME}"
