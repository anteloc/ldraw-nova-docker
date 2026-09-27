#!/bin/bash
mjs="/opt/mpd2glb/mpd2glb.mjs"

# If not available at the given path, try and set the path the source repository, cloned as a sibling directory.
if [ ! -f "$mjs" ]; then
  mjs="$(dirname "$0")/../mpd2glb/mpd2glb.mjs"
fi

if [ ! -f "$mjs" ]; then
  echo "Error: mpd2glb.mjs not found at '$mjs'" >&2
  echo "See: https://github.com/anteloc/mpd2glb"
  exit 1
fi

# exec: bun takes this process's place, so stopping it (e.g. the web app's
# time limit) stops the conversion too.
exec bun "$mjs" "$@"
