#!/usr/bin/env bash
set -euo pipefail

# Build Alpaca MicroPython kernel for RP2040 (Raspberry Pi Pico/Pico W)
# This script assumes it's run from the repository root inside the container.

ROOT_DIR=$(pwd)
OUT_DIR="$ROOT_DIR/dist"
mkdir -p "$OUT_DIR"

# Tag determination: prefer TAG env (from GitHub Actions), then GITHUB_REF_NAME,
# then try git describe, finally fall back to UTC date.
TAG="${TAG:-${GITHUB_REF_NAME:-}}"
if [ -z "$TAG" ]; then
  if git describe --tags --exact-match >/dev/null 2>&1; then
    TAG=$(git describe --tags --exact-match)
  else
    TAG=$(git describe --tags --always 2>/dev/null || date -u +%Y%m%d)
  fi
fi

# Fix Git ownership issues in Docker containers
echo "==> Configuring Git safe directory"
git config --global --add safe.directory "$ROOT_DIR" || true

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
# You can set BOARD=RPI_PICO or RPI_PICO_W via env var BOARD, default to RPI_PICO
: "${BOARD:=RPI_PICO}"
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

# Copy artifact to dist with requested name
DEST_NAME="alpaca_firmware${TAG}.uf2"
cp "ports/rp2/${FOUND_UF2}" "${OUT_DIR}/${DEST_NAME}"

echo "==> Build finished: ${OUT_DIR}/${DEST_NAME}"
