#!/usr/bin/env bash
set -euo pipefail

TEMPLATE="$1"
OUTPUT="$2"

# Replace placeholders
sed \
  -e "s|YOUR_GOOGLE_CLIENT_ID|${GOOGLE_CLIENT_ID}|g" \
  -e "s|YOUR_GOOGLE_CLIENT_SECRET|${GOOGLE_CLIENT_SECRET}|g" \
  -e "s|YOUR_DROPBOX_CLIENT_ID|${DROPBOX_CLIENT_ID}|g" \
  -e "s|YOUR_DROPBOX_CLIENT_SECRET|${DROPBOX_CLIENT_SECRET}|g" \
  "$TEMPLATE" > "$OUTPUT"
