# check=skip=FromPlatformFlagConstDisallowed
# LeoCAD (pinned released AppImage) + Python + full LDraw parts library,
# plus a web app (chat with LLM agents that build and render LDraw models).
#
# No compiling: downloads an official, tagged LeoCAD-Linux-*.AppImage release
# and unpacks its embedded squashfs (no FUSE / --device needed), and bakes
# in the complete official LDraw parts library.
#
# Build and run (see docker-compose.yml / README.md):
#   docker compose up -d --build        # web app on http://localhost:8765
#   docker compose exec leocad-app bash # log in
#
# Pin versions explicitly:
#   docker build --build-arg LEOCAD_TAG=v25.09 -t leocad-app .

# --- Stage 1: the web UI (React + Vite) --------------------------------------
# Runs on the build host's own architecture (fast, no emulation); its output is
# plain static files, so it doesn't matter that the final image is amd64.
FROM --platform=$BUILDPLATFORM node:24-slim AS frontend
WORKDIR /src
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/frontend/ ./
RUN npm run build

# --- Stage 2: the runtime image ----------------------------------------------
# LeoCAD only publishes x86_64 Linux AppImages, so the image is always amd64.
# On Apple Silicon / arm64 hosts Docker Desktop runs it under emulation.
FROM --platform=linux/amd64 ubuntu:24.04

# Pin to a specific, released (non-continuous) LeoCAD version.
# Check https://github.com/leozide/leocad/releases for available tags.
ARG LEOCAD_TAG=v25.09

# The 3D viewer: library.ldraw.org's own source (MIT), which vendors the
# buildinginstructions.js viewer (Unlicense) it runs on. Pinned commit.
ARG LDRAWORG_REF=a38efc7aca5b1171e888687939d77b6c0b228c7f

ENV DEBIAN_FRONTEND=noninteractive

# --- Runtime deps: Xvfb/Mesa for headless GL, Qt's X11 plugin deps, Python,
# plus curl/unzip just to fetch and unpack things during the build. ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl unzip squashfs-tools \
        xvfb x11-utils \
        libgl1 libglx-mesa0 libegl1 libgl1-mesa-dri libosmesa6 \
        libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
        libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
        libxcb-xinerama0 libnss3 libdbus-1-3 fontconfig \
        python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# --- Download the pinned release's AppImage and unpack it --------------------
# An AppImage is an ELF runtime with a squashfs image appended right after its
# section headers. We unpack that squashfs directly instead of running
# `./LeoCAD.AppImage --appimage-extract`: the AppImage's "AI\x02" marker in the
# ELF header padding makes emulated (e.g. Apple Silicon) builds fail with
# "Exec format error", and this way nothing is executed at build time at all.
RUN set -eux; \
    rel_json="$(curl -fsSL "https://api.github.com/repos/leozide/leocad/releases/tags/${LEOCAD_TAG}")"; \
    asset_url="$(printf '%s' "$rel_json" | grep -oP '"browser_download_url":\s*"\K[^"]*x86_64\.AppImage' | head -n1)"; \
    test -n "$asset_url"; \
    echo "Downloading: ${asset_url}"; \
    curl -fsSL "$asset_url" -o /tmp/LeoCAD.AppImage; \
    offset="$(python3 -c 'import struct,sys; h=open(sys.argv[1],"rb").read(64); shoff,=struct.unpack_from("<Q",h,0x28); shentsize,shnum=struct.unpack_from("<HH",h,0x3A); print(shoff+shentsize*shnum)' /tmp/LeoCAD.AppImage)"; \
    echo "squashfs offset: ${offset}"; \
    mkdir -p /opt/leocad; \
    unsquashfs -q -no-progress -o "$offset" -d /opt/leocad/squashfs-root /tmp/LeoCAD.AppImage; \
    rm /tmp/LeoCAD.AppImage; \
    ln -s /opt/leocad/squashfs-root/AppRun /usr/local/bin/leocad

# --- Bake in the complete official LDraw parts library ----------------------
# Produces /opt/ldraw/ldraw/{parts,p,models,LDConfig.ldr,...}
RUN mkdir -p /opt/ldraw \
    && curl -fsSL https://library.ldraw.org/library/updates/complete.zip -o /tmp/complete.zip \
    && unzip -q /tmp/complete.zip -d /opt/ldraw \
    && rm /tmp/complete.zip

# LeoCAD reads LEOCAD_LIB as its default parts-library path (equivalent to
# always passing --libpath). Any call can still override it with -l/--libpath.
ENV LEOCAD_LIB=/opt/ldraw/ldraw

# --- The 3D viewer's JavaScript, textures and licence ------------------------
# -> /opt/web/viewer-vendor/{ldbi/js,ldbi/textures,js/ldraworgscene.js,js/WebGL.js}
RUN set -eux; \
    mkdir -p /tmp/lor /opt/web/viewer-vendor/js; \
    curl -fsSL "https://codeload.github.com/ldraw-org/ldraworg-library/tar.gz/${LDRAWORG_REF}" \
        | tar -xz -C /tmp/lor --strip-components=1 --wildcards '*/public/assets/*' '*/LICENSE'; \
    cp -r /tmp/lor/public/assets/ldbi /opt/web/viewer-vendor/ldbi; \
    cp /tmp/lor/public/assets/js/ldraworgscene.js /tmp/lor/public/assets/js/WebGL.js /opt/web/viewer-vendor/js/; \
    cp /tmp/lor/LICENSE /opt/web/viewer-vendor/LICENSE-ldraworg-library.txt; \
    rm -rf /tmp/lor

# --- Bake in the annotated LDraw models -------------------------------------
# Lives in the image (not in /data), so it's always there regardless of what
# the host mounts. Placed before the app code so editing scripts doesn't
# invalidate this (large) layer.
COPY models-annotated/ /opt/models-annotated/

# Search indexes for the agent tools (parts descriptions, reference models).
# Only depends on the two trees above, so app edits don't rebuild it.
COPY web/backend/build_index.py /opt/index/build_index.py
RUN python3 /opt/index/build_index.py /opt/ldraw/ldraw /opt/models-annotated /opt/index

# Software (llvmpipe) OpenGL rendering — works on any host, GPU or not.
ENV LIBGL_ALWAYS_SOFTWARE=1

# entrypoint.sh starts Xvfb on this display. It's set as image ENV (rather
# than only exported by the entrypoint) so shells opened with `docker exec`,
# which bypass the entrypoint, can run leocad too.
ENV DISPLAY=:99

# Qt warns on every call without a (0700) runtime dir; give it one up front.
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
RUN mkdir -p -m 0700 "${XDG_RUNTIME_DIR}"

# --- Users: the server runs as root; agent-written code runs as `agent` -------
# /config holds LLM API keys: root-only, so agent code can't read them.
RUN useradd --system --create-home --shell /bin/bash agent \
    && install -d -m 0700 -o agent -g agent /tmp/runtime-agent \
    && install -d -m 0700 /config

# --- Python side of the app ---------------------------------------------------
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
ENV PYTHONPATH=/app
COPY leocad_render.py example.py /app/
COPY web/backend/ /app/web/backend/
COPY web/viewer/ /opt/web/viewer/
COPY --from=frontend /src/dist/ /opt/web/static/

# --- Shared folder with the host --------------------------------------------
# /data/generated: the model collection; /data/chats: chat history;
# /data/output: agents' work folders (one per chat) and the CLI's default output.
RUN mkdir -p /data/generated /data/chats /data/output
VOLUME ["/data", "/config"]

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--app-dir", "/app/web/backend", "--host", "0.0.0.0", "--port", "8000"]
