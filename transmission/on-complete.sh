#! /bin/bash
set -euo pipefail

echo "Transmission download completed. Notifying organizer to scan."
echo "Transmission info: torrent_dir=$TR_TORRENT_DIR, torrent_name=$TR_TORRENT_NAME"

URL="http://organizer:8000/scan-once"

for attempt in 1 2 3 4 5; do
  echo "Attempt $attempt to notify organizer at $URL"
  curl -s -X POST http://organizer:8000/scan-once >/dev/null 2>&1 && exit 0
done

echo "Notified"
