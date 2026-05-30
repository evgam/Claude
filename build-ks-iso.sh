#!/usr/bin/env bash
# build-ks-iso.sh — Embed a kickstart file into a RHEL 9 ISO
#
# Usage:
#   ./build-ks-iso.sh -s rhel-9.x-x86_64-dvd.iso [-k rhel9-kickstart.cfg] [-o rhel9-ks.iso]
#
# Requirements (install with: dnf install xorriso syslinux isomd5sum):
#   xorriso, isohybrid (syslinux-utils), implantisomd5 (isomd5sum)

set -euo pipefail

###############################################################################
# Defaults
###############################################################################
KS_FILE="rhel9-kickstart.cfg"
OUTPUT_ISO="rhel9-ks.iso"
SOURCE_ISO=""
WORK_DIR=""

###############################################################################
# Usage
###############################################################################
usage() {
    cat <<EOF
Usage: $(basename "$0") -s <source.iso> [-k <kickstart.cfg>] [-o <output.iso>]

  -s  Source RHEL 9 ISO (required)
  -k  Kickstart file  (default: rhel9-kickstart.cfg)
  -o  Output ISO path (default: rhel9-ks.iso)
  -h  Show this help
EOF
    exit 1
}

###############################################################################
# Argument parsing
###############################################################################
while getopts ":s:k:o:h" opt; do
    case $opt in
        s) SOURCE_ISO="$OPTARG" ;;
        k) KS_FILE="$OPTARG"   ;;
        o) OUTPUT_ISO="$OPTARG" ;;
        h) usage ;;
        :) echo "ERROR: -$OPTARG requires an argument."; usage ;;
        *) echo "ERROR: Unknown option -$OPTARG"; usage ;;
    esac
done

###############################################################################
# Pre-flight checks
###############################################################################
[[ -z "$SOURCE_ISO" ]] && { echo "ERROR: -s <source.iso> is required."; usage; }
[[ -f "$SOURCE_ISO" ]] || { echo "ERROR: Source ISO not found: $SOURCE_ISO"; exit 1; }
[[ -f "$KS_FILE"    ]] || { echo "ERROR: Kickstart file not found: $KS_FILE"; exit 1; }

for tool in xorriso isohybrid implantisomd5; do
    command -v "$tool" &>/dev/null || {
        echo "ERROR: '$tool' not found. Install with: dnf install xorriso syslinux isomd5sum"
        exit 1
    }
done

if [[ -f "$OUTPUT_ISO" ]]; then
    read -r -p "Output file '$OUTPUT_ISO' already exists. Overwrite? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
fi

###############################################################################
# Setup working directory
###############################################################################
WORK_DIR=$(mktemp -d /tmp/ks-iso-XXXXXX)
MOUNT_DIR="$WORK_DIR/mnt"
ISO_DIR="$WORK_DIR/iso"

cleanup() {
    echo "Cleaning up $WORK_DIR ..."
    mountpoint -q "$MOUNT_DIR" && umount "$MOUNT_DIR" 2>/dev/null || true
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

mkdir -p "$MOUNT_DIR" "$ISO_DIR"

###############################################################################
# Mount and copy the source ISO
###############################################################################
echo "==> Mounting $SOURCE_ISO ..."
mount -o loop,ro "$SOURCE_ISO" "$MOUNT_DIR"

echo "==> Copying ISO contents (this may take a minute) ..."
cp -aT "$MOUNT_DIR" "$ISO_DIR"
chmod -R u+w "$ISO_DIR"

umount "$MOUNT_DIR"

###############################################################################
# Embed the kickstart file
###############################################################################
echo "==> Embedding kickstart file as /ks.cfg ..."
cp "$KS_FILE" "$ISO_DIR/ks.cfg"

###############################################################################
# Patch BIOS boot menu (isolinux)
###############################################################################
ISOLINUX_CFG="$ISO_DIR/isolinux/isolinux.cfg"
if [[ -f "$ISOLINUX_CFG" ]]; then
    echo "==> Patching isolinux/isolinux.cfg ..."
    # Set timeout to 50 (5 seconds) so it doesn't wait forever
    sed -i 's/^timeout .*/timeout 50/' "$ISOLINUX_CFG"
    # Inject inst.ks into the first 'append' line that contains 'inst.stage2'
    sed -i '/inst\.stage2/s|$| inst.ks=cdrom:/ks.cfg|' "$ISOLINUX_CFG"
fi

###############################################################################
# Patch UEFI boot menu (GRUB2)
###############################################################################
GRUB_CFG="$ISO_DIR/EFI/BOOT/grub.cfg"
if [[ -f "$GRUB_CFG" ]]; then
    echo "==> Patching EFI/BOOT/grub.cfg ..."
    sed -i '/inst\.stage2/s|$| inst.ks=cdrom:/ks.cfg|' "$GRUB_CFG"
    # Reduce menu timeout to 5 seconds
    sed -i 's/^set timeout=.*/set timeout=5/' "$GRUB_CFG"
fi

###############################################################################
# Extract boot catalogue metadata from the original ISO with xorriso
###############################################################################
echo "==> Reading boot catalogue from source ISO ..."
BOOT_CAT=$(xorriso -indev "$SOURCE_ISO" -report_el_torito plain 2>/dev/null \
    | awk '/^El Torito boot catalogue/{found=1} found && /Catalog/{print $NF; exit}' || true)

# Fallback: common RHEL path
[[ -z "$BOOT_CAT" ]] && BOOT_CAT="isolinux/boot.cat"

###############################################################################
# Rebuild the ISO
###############################################################################
echo "==> Building $OUTPUT_ISO ..."
xorriso -as mkisofs \
    -iso-level 3 \
    -full-iso9660-filenames \
    -volid "RHEL-9-KS" \
    -eltorito-boot isolinux/isolinux.bin \
    -eltorito-catalog "$BOOT_CAT" \
    -no-emul-boot \
    -boot-load-size 4 \
    -boot-info-table \
    -eltorito-alt-boot \
    -e images/efiboot.img \
    -no-emul-boot \
    -isohybrid-gpt-basdat \
    -output "$OUTPUT_ISO" \
    "$ISO_DIR"

###############################################################################
# Make it a hybrid ISO (bootable from USB as well as optical drive)
###############################################################################
echo "==> Making hybrid ISO (USB-bootable) ..."
isohybrid --uefi "$OUTPUT_ISO" 2>/dev/null || isohybrid "$OUTPUT_ISO"

###############################################################################
# Embed MD5 checksum (dracut will verify this on boot)
###############################################################################
echo "==> Implanting ISO MD5 checksum ..."
implantisomd5 "$OUTPUT_ISO"

###############################################################################
# Done
###############################################################################
SIZE=$(du -sh "$OUTPUT_ISO" | cut -f1)
echo ""
echo "Done! Output: $OUTPUT_ISO ($SIZE)"
echo ""
echo "Write to USB:  dd if=$OUTPUT_ISO of=/dev/sdX bs=4M status=progress oflag=sync"
echo "Burn to DVD:   wodim -v dev=/dev/sr0 $OUTPUT_ISO"
