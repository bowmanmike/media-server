#! /bin/bash
set -euo pipefail

echo "[on-complete] Transmission download completed. Notifying organizer to scan."
echo "[on-complete] Transmission info: torrent_dir=$TR_TORRENT_DIR, torrent_name=$TR_TORRENT_NAME"

URL="http://organizer:8000/scan-once"

for attempt in 1 2 3 4 5; do
  echo "[on-complete] Attempt $attempt: sending trigger"

  # Log curl output (status code + body)
  RESPONSE=$(curl -s -w " HTTP_STATUS:%{http_code}" -X POST "$URL")
  CURL_EXIT=$?

  echo "[on-complete] Response: $RESPONSE (curl exit code: $CURL_EXIT)"

  # Extract status code
  STATUS=$(echo "$RESPONSE" | sed -E 's/.*HTTP_STATUS:([0-9]+)$/\1/')

  if [ "$CURL_EXIT" -eq 0 ] && [ "$STATUS" = "200" ]; then
    echo "[on-complete] Organizer acknowledged successfully (HTTP 200)"
    exit 0
  fi

  echo "[on-complete] Trigger failed (status $STATUS), retrying..."
  sleep $((attempt * 2))e
done

echo "[on-complete] Notified"
