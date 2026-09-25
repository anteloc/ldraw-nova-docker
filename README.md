# LeoCAD + Python in one container (headless LDraw rendering)

A single image containing:
- **A web app** on http://localhost:8765: chat with LLM agents (Claude,
  GPT, Gemini, local Ollama models — anything LiteLLM supports) that design
  LDraw models, render them with LeoCAD and show you screenshots you can open
  in a three.js 3D viewer. See [Web app](#web-app).
- **LeoCAD**, installed from an official, pinned, *released* AppImage (not
  built from source, not the rolling "continuous" build) — no compiler, no
  build failures from work-in-progress code
- **The complete official LDraw parts library**, downloaded from
  library.ldraw.org and baked into the image
- **Python 3**, so your own scripts run in the same container and call
  `leocad` as a subprocess (see `leocad_render.py`)
- **The annotated models** from `models-annotated/`, baked into the image at
  `/opt/models-annotated/`
- **A persistent virtual display** (Xvfb), started once by the entrypoint for
  the life of the container, since LeoCAD's render mode needs a real
  (virtual, here) display even from the CLI
- **A shared folder**, `/data`, bind-mounted from the host's `./data`:
  everything under it is input, and rendered images go to `data/output/`

## Layout

```
.
├── Dockerfile
├── entrypoint.sh          # starts Xvfb once, then execs the main process
├── docker-compose.yml     # runs the web app; you can log into the container any time
├── docker-compose.dev.yml # development overlay: live backend code + auto-reload
├── requirements.txt
├── leocad_render.py       # render_image() + a CLI — wrapper around leocad
├── example.py             # batch worker: renders everything under data/ -> data/output/
├── models-annotated/      # baked into the image at /opt/models-annotated/
├── web/
│   ├── backend/           # FastAPI: chat API, agent loop (LiteLLM), tools, file routes
│   ├── frontend/          # React + Vite UI (built in a Docker build stage)
│   └── viewer/            # viewer.html: the three.js LDraw viewer page
└── data/                  # mounted at /data (not baked in)
    ├── generated/<chat>/  # models the agents made (also each chat's working folder)
    └── output/            # rendered images land here (output/generated/<chat>/ for chats)
```

| Host | Container | |
|---|---|---|
| `./data/` | `/data/` | input: any `.ldr`/`.mpd` anywhere under it |
| `./data/output/` | `/data/output/` | output: rendered PNGs |
| `./models-annotated/` | `/opt/models-annotated/` | baked in at build time (rebuild to update) |
| named volume `config` | `/config/` | LLM settings, API keys, chat history (not on the host, on purpose) |

## Why an AppImage, not Snap/Flatpak, and not a source build

- **Snap** needs `snapd` (normally systemd too) to install and confine
  packages — awkward to stand up inside a plain container.
- **Flatpak** needs the `flatpak` tool plus an OSTree runtime (the
  freedesktop platform runtime alone is several hundred MB) and leans on
  `bwrap` for sandboxing, which nests uncomfortably inside Docker's own
  container namespaces.
- **AppImage** is a single self-contained file: a small ELF runtime with a
  squashfs image appended. The build unpacks that squashfs with
  `unsquashfs` to a plain directory — no FUSE, no `--device /dev/fuse`,
  no extra `--cap-add`, and nothing left mounted at runtime. (It doesn't use
  `./LeoCAD.AppImage --appimage-extract`, because under emulation that
  fails with "Exec format error"; see *Apple Silicon* below.)
- Building from source gets you a bleeding-edge (possibly broken) checkout
  and adds a compiler + Qt dev headers to the build. Downloading a **tagged**
  release's AppImage instead gives you an actual stable, released version,
  with none of that.

## Build

```bash
docker build -t leocad-app .
# pin a specific stable release explicitly (check
# https://github.com/leozide/leocad/releases for available tags):
docker build --build-arg LEOCAD_TAG=v25.09 -t leocad-app .
```

The build script resolves the AppImage's exact asset URL from the GitHub API
for that tag rather than hardcoding a filename, since asset naming has
varied slightly across releases.

### Apple Silicon / arm64 hosts

LeoCAD only publishes **x86_64** Linux AppImages, so the image is always
built as `linux/amd64` (`FROM --platform=linux/amd64` in the Dockerfile,
`platform: linux/amd64` in compose). Docker Desktop runs it under
emulation. It works, but renders are slower than on a native x86_64 host.

## Run

### Log into a running container and render by hand

```bash
docker compose up -d --build              # start it (the web server keeps it up)
docker compose exec leocad-app bash       # log in — repeat as often as you like
```

Inside the container:

```bash
python3 /app/leocad_render.py /opt/models-annotated/8303-1.mpd
#   -> /data/output/8303-1.png, i.e. ./data/output/8303-1.png on the host

python3 /app/leocad_render.py /opt/models-annotated/316-1.mpd /opt/models-annotated/854-1.mpd \
    --width 1920 --height 1080 --camera-angles 20 60
python3 /app/leocad_render.py /data/my-model.ldr -o /data/output/tests
python3 /app/leocad_render.py --help

python3 /app/example.py                   # render everything under /data
```

Open `./data/output/` on the host to look at the results. When you're done:

```bash
docker compose down
```

### One-off runs

```bash
docker run --rm -it --init -v "$PWD/data:/data" leocad-app bash
docker run --rm --init -v "$PWD/data:/data" leocad-app python3 /app/example.py
docker compose run --rm leocad-app python3 /app/example.py
```

`example.py` finds every `.ldr`/`.mpd` anywhere under `/data` (skipping
`/data/output` itself) and mirrors the folder layout into the output:
`data/sets/car.mpd` → `data/output/sets/car.png`.

`--init` matters: the entrypoint runs Xvfb in the background *and* your main
process in the foreground, so you want Docker's built-in init to reap
zombies and forward signals correctly.

Raw `leocad` calls still work directly (no `--libpath` needed — see below):

```bash
docker run --rm --init -v "$PWD/data:/data" leocad-app \
    leocad /data/car.ldr -i /data/output/car.png -w 1280 -h 720 --camera-angles 30 40
```

## Web app

```bash
docker compose up -d --build
open http://localhost:8765                # port: LEOCAD_WEB_PORT in .env
```

1. **Settings → Add model.** Pick a preset or type any LiteLLM model string
   (`anthropic/claude-sonnet-5`, `openai/<model>`, `gemini/<model>`,
   `ollama_chat/<model>` with API base `http://host.docker.internal:11434`,
   any OpenAI-compatible server, …), an API key, and optionally extra LiteLLM
   parameters. **Test** sends a one-word request. Keys can also stay out of
   the UI: put `ANTHROPIC_API_KEY=...` in a `.env` file next to
   `docker-compose.yml` and enter `os.environ/ANTHROPIC_API_KEY` as the key.
   Existing LiteLLM proxy `model_list` YAML can be imported.
2. **Chat.** Ask for a model. The agent searches the parts library and the
   ~1800 annotated reference models, writes an `.mpd`, validates it (unknown
   parts, bad colours), renders it with LeoCAD and — if the model accepts
   images — looks at its own render to fix problems. It can also run Python or
   shell in its chat folder (e.g. to generate a model with a script); any
   `.ldr`/`.mpd` it writes there is rendered automatically.
3. **Screenshots** appear in the chat. Click one for the 3D viewer, or
   download the `.mpd`/`.png`. **Models** lists every generated model,
   **Outputs** browses `data/output` (single files or a folder as `.zip`),
   and the sidebar keeps the chat history with thumbnails.

Where things live:

| What | Where |
|---|---|
| Generated models | `data/generated/<chat>/<name>-v<N>.mpd` — never overwritten, so old chats keep their versions |
| Their screenshots | `data/output/generated/<chat>/<name>-v<N>.png` (same mapping as `example.py`) |
| Other renders by the agent | `data/output/generated/<chat>/renders/` |
| Scripts the agent ran | `data/generated/<chat>/.scripts/` |
| LLM settings, keys, chat history | `/config` volume (`docker compose down -v` deletes it) |

**The 3D viewer** is `/viewer/viewer.html?model=<url>` — e.g.
http://localhost:8765/viewer/viewer.html?model=/ref/8303-1.mpd for a
reference model. It is library.ldraw.org's viewer
([ldraworg-library](https://github.com/ldraw-org/ldraworg-library), MIT, built
on [buildinginstructions.js](https://github.com/LasseD/buildinginstructions.js),
Unlicense), vendored into the image at a pinned commit (`LDRAWORG_REF`), with
parts served from the baked-in library instead of ldraw.org.

**Security.** This is a local, single-user tool:

* The port is bound to `127.0.0.1` only. There is no login, and anyone who
  can reach it can spend your API keys and run code in the container.
* Agent code runs as the unprivileged `agent` user with a scrubbed environment
  and CPU/file-size limits. It can't read `/config` (keys, history) but can
  read and write everything in `/data`, and it has network access.
* For stronger isolation, move `web/backend/sandbox.py`'s execution into a
  separate container with only `data/generated` mounted and no network.

### Developing the web app

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d   # backend from your checkout, auto-reload
cd web/frontend && npm install && npm run dev                          # UI with hot reload: http://localhost:5173

# backend tests (inside the container: they use LeoCAD and the real library)
docker compose exec leocad-app bash -c \
  "pip install -q --break-system-packages -r /app/web/backend/requirements-dev.txt && cd /app/web/backend && pytest -q"
```

The agent's instructions are in `web/backend/prompts/system.md` and its tools
in `web/backend/tools.py`.

## The parts library

`complete.zip` from library.ldraw.org is unzipped at build time to
`/opt/ldraw/ldraw/` (containing `parts/`, `p/`, `models/`, `LDConfig.ldr`,
etc.). The image sets:

```
ENV LEOCAD_LIB=/opt/ldraw/ldraw
```

`LEOCAD_LIB` is LeoCAD's documented environment-variable equivalent of
`-l/--libpath`, so every `leocad` call in the container — from Python, from
`docker run ... leocad ...` directly, from anywhere — finds parts
automatically, with no flag needed. Pass `-l/--libpath` (or `libpath=` in
`render_image()`) only if a particular call needs a *different* library.

Note this makes the image noticeably larger than the earlier `library.bin`
approach, since it's the full official library rather than LeoCAD's compact
cache format — that's the deliberate trade-off for having the complete,
canonical parts set baked in.

## Using LeoCAD from your own Python code

```python
from leocad_render import render_image

render_image("/data/car.ldr", "/data/output/car.png", width=1920, height=1080)
```

See `leocad_render.py` for the full parameter list (submodel, step
range, orthographic, a one-off `libpath` override, extra raw args, timeout).
Add your own dependencies to `requirements.txt`. Scripts are copied into the
image at `/app`, so rebuild (`docker compose up -d --build`) after editing
them.

## Useful LeoCAD CLI flags

| Flag | Purpose |
|---|---|
| `-i, --image <file.ext>` | Render and save an image (`png`, `jpg`, `bmp`, `gif`); exits when done |
| `-w, --width <px>` / `-h, --height <px>` | Output image size |
| `-l, --libpath <path>` | Override the parts library for this call (defaults to `$LEOCAD_LIB`) |
| `-s, --submodel <name>` | Render a specific submodel |
| `-c, --camera <name>` | Use a named camera from the file |
| `--viewpoint front\|back\|left\|right\|top\|bottom\|home` | Preset camera angle |
| `--camera-angles <lat> <lon>` | Orbit camera around the model, in degrees |
| `--camera-position[-ldraw] x y z tx ty tz ux uy uz` | Explicit camera position/target/up |
| `--orthographic` | Orthographic instead of perspective projection |
| `--fov <deg>` | Field of view |
| `--aa-samples <1\|2\|4\|8>` | Anti-aliasing |
| `-ss, --stud-style <0-7>` | Stud rendering style |
| `-f, --from <step>` / `-t, --to <step>` | Render a range of build steps |

Full reference: `docker run --rm leocad-app leocad --help`, or
https://www.leocad.org/docs/cli.html

## Notes

* **Concurrency**: one Xvfb per container, so one `leocad` process at a time
  per container (the web app queues its renders). For parallel renders, run
  multiple containers rather than parallelizing `leocad` calls inside a
  single one.
* **Shared `/data`**: if other processes/containers also read/write it
  concurrently, handle that as you would any shared filesystem (temp name +
  rename, or per-job subfolders) — nothing here adds locking on top of it.
* **Real GPU**: `LIBGL_ALWAYS_SOFTWARE=1` forces Mesa's software renderer
  (llvmpipe), which works on any host. For heavier workloads, drop that env
  var and run with `--device /dev/dri` (plus matching drivers) for real GPU
  acceleration.
* **`docker exec` shells** skip the entrypoint, so they don't start their
  own Xvfb. They use the container's existing one through `DISPLAY=:99`,
  which is set as image `ENV`.
* **Updating the pinned version**: bump `LEOCAD_TAG` and rebuild. Nothing
  else in the image needs to change for that.
