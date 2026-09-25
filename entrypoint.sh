#!/usr/bin/env bash
# Starts one Xvfb for the lifetime of the container (instead of spinning one
# up per `leocad` call), then execs whatever the container's main process is
# — a shell, a Python worker script, `sleep infinity`, or a direct
# `leocad ...` invocation.
#
# DISPLAY comes from the image ENV (see Dockerfile) so that `docker exec`
# shells, which skip this script, point at the same Xvfb.
set -euo pipefail

export DISPLAY="${DISPLAY:-:99}"

# A stopped-then-restarted container keeps its filesystem, including the
# previous Xvfb's lock/socket, which would make the new Xvfb refuse to start.
DISPLAY_NUM="${DISPLAY#:}"
rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}"

Xvfb "${DISPLAY}" -screen 0 1920x1080x24 &
XVFB_PID=$!

cleanup() {
    kill "${XVFB_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for the X server to actually be ready before handing off.
for _ in $(seq 1 50); do
    if xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
        break
    fi
    sleep 0.1
done

exec "$@"
