#!/bin/sh

PORT_FILE=/gluetun/forwarded_port
RPC=http://gluetun:9091/transmission/rpc
LAST_PORT=""

echo "Waiting for Proton forwarded port..."

while true; do
    if [ -f "$PORT_FILE" ]; then
        PORT=$(cat "$PORT_FILE")

        if [ -n "$PORT" ] && [ "$PORT" != "$LAST_PORT" ]; then
            echo "Forwarded port is $PORT; updating Transmission..."

            # First request intentionally receives HTTP 409 and gives us
            # Transmission's required session ID.
            SESSION_ID=$(
                curl -s -D - -o /dev/null "$RPC" |
                awk -F': ' 'tolower($1) == "x-transmission-session-id" {
                    gsub("\r", "", $2)
                    print $2
                }'
            )

            if [ -n "$SESSION_ID" ]; then
                RESULT=$(
                    curl -s \
                        -H "X-Transmission-Session-Id: $SESSION_ID" \
                        -H "Content-Type: application/json" \
                        --data "{\"method\":\"session-set\",\"arguments\":{\"peer-port\":$PORT}}" \
                        "$RPC"
                )

                echo "$RESULT"

                case "$RESULT" in
                    *'"result":"success"'*)
                        echo "Transmission peer port set to $PORT"
                        LAST_PORT="$PORT"
                        ;;
                    *)
                        echo "Transmission rejected update; will retry."
                        ;;
                esac
            else
                echo "Transmission RPC isn't ready; will retry."
            fi
        fi
    fi

    sleep 10
done
