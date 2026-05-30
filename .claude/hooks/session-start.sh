#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code on the web environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

###############################################################################
# 1. Install ISO build tools
###############################################################################
PACKAGES_NEEDED=()
command -v xorriso      &>/dev/null || PACKAGES_NEEDED+=(xorriso)
command -v isohybrid    &>/dev/null || PACKAGES_NEEDED+=(syslinux-utils)
# isomd5sum is a Fedora package; on Ubuntu the equivalent is isomd5sum (universe)
dpkg -s isomd5sum &>/dev/null 2>&1   || PACKAGES_NEEDED+=(isomd5sum)

if [ ${#PACKAGES_NEEDED[@]} -gt 0 ]; then
  echo "Installing: ${PACKAGES_NEEDED[*]}"
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${PACKAGES_NEEDED[@]}"
else
  echo "ISO build tools already installed."
fi

###############################################################################
# 2. Download RHEL 9 ISO if a URL is configured
###############################################################################
ISO_DEST="/home/user/Claude/rhel9.iso"

if [ -z "${RHEL9_ISO_URL:-}" ]; then
  echo "RHEL9_ISO_URL is not set — skipping ISO download."
  echo "Set it in your environment settings to enable automatic ISO download."
  exit 0
fi

if [ -f "$ISO_DEST" ]; then
  echo "ISO already present at $ISO_DEST — skipping download."
  exit 0
fi

echo "Downloading RHEL 9 ISO from \$RHEL9_ISO_URL ..."
curl -fL --progress-bar \
     --retry 3 --retry-delay 5 \
     -o "${ISO_DEST}.tmp" \
     "$RHEL9_ISO_URL"

mv "${ISO_DEST}.tmp" "$ISO_DEST"
echo "ISO saved to $ISO_DEST ($(du -sh "$ISO_DEST" | cut -f1))"
