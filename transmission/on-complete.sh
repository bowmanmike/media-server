#! /bin/bash
set -euo pipefail

echo "Transmission download completed. Notifying organizer to scan."
echo "Transmission info: torrent_dir=$TR_TORRENT_DIR, torrent_name=$TR_TORRENT_NAME"
curl -s -X POST http://organizer:8000/scan-once >/dev/null 2>&1

echo "Notified"
