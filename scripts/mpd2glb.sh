#!/bin/bash
mjs="/opt/mpd2glb/mpd2glb.mjs"

# exec: bun takes this process's place, so stopping it (e.g. the web app's
# time limit) stops the conversion too.
exec bun "$mjs" "$@"
