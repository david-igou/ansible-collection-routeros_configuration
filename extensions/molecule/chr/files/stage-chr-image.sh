#!/usr/bin/env bash
# Stage a MikroTik CHR raw image as qcow2 for the molecule qemu provisioner.
# CHR ships a zipped raw .img; the qemu role consumes qcow2, so we convert.
# Idempotent: skips download/convert if the qcow2 already exists.
# Prints the absolute qcow2 path on stdout (and nothing else on success).
set -euo pipefail

CHR_VERSION="${CHR_VERSION:?set CHR_VERSION, e.g. 7.21.4}"
CACHE_DIR="${CHR_CACHE_DIR:-$HOME/.cache/chr-images}"
ZIP_URL="https://download.mikrotik.com/routeros/${CHR_VERSION}/chr-${CHR_VERSION}.img.zip"

mkdir -p "$CACHE_DIR"
zip_path="$CACHE_DIR/chr-${CHR_VERSION}.img.zip"
qcow2_path="$CACHE_DIR/chr-${CHR_VERSION}.qcow2"

if [[ -f "$qcow2_path" ]]; then
  echo "$qcow2_path"
  exit 0
fi

[[ -f "$zip_path" ]] || curl -fSL -o "$zip_path" "$ZIP_URL"

# CHR zip contains a single chr-<ver>.img raw disk
img_inside="$(unzip -Z1 "$zip_path" | grep -E '\.img$' | head -1)"
[[ -n "$img_inside" ]] || { echo "no .img found inside $zip_path" >&2; exit 1; }
unzip -o "$zip_path" -d "$CACHE_DIR" >/dev/null
raw_path="$CACHE_DIR/$img_inside"

qemu-img convert -f raw -O qcow2 "$raw_path" "$qcow2_path"
echo "$qcow2_path"
