# LDraw Astra + Python in one container (headless LDraw rendering)

A single image containing:
- **A web app** on http://localhost:8765: chat with LLM agents (Claude,
  GPT, Gemini, local Ollama models — anything LiteLLM supports) that design
  LDraw models, render them with LeoCAD and show you screenshots you can open
  in a three.js 3D viewer, in a 3D player that animates how the model is
  built, or in mixed reality on a Meta Quest 3. See [Web app](#web-app).
- **LeoCAD**, installed from an official, pinned, *released* AppImage (not
  built from source, not the rolling "continuous" build) — no compiler, no
  build failures from work-in-progress code
- **The complete official LDraw parts library**, downloaded from
  library.ldraw.org and baked into the image
- **Python 3**, so your own scripts run in the same container and call
  `leocad` as a subprocess (see `leocad_render.py`)
- **The annotated models** from `models-annotated/`, baked into the image at
  `/opt/models-annotated/`
- **The demo models** from `models-demo/`, baked into the image at
  `/opt/models-demo/` and shown on the Models page
- **[mpd2glb](https://github.com/anteloc/mpd2glb)** (pinned release, run with
  a pinned [Bun](https://bun.com/) through `scripts/mpd2glb.sh`), which converts LDraw models to glTF `.glb` while keeping
  the LDraw metadata (descriptions, part files, colours, building steps) on
  every node
- **`scripts/`**, at `/opt/scripts/` and on the `PATH` (the agents' too):
  `mpd2glb.sh` (the way to run mpd2glb, whatever runs it underneath),
  `ldraw-render-steps.sh` (a picture per building step, with LeoCAD) and
  `ldraw-info.db` (SQLite: LDraw parts and models with descriptions,
  categories, keywords, bounding boxes and colours, full-text indexes, and
  views for jev-rerank)
- **[uv](https://docs.astral.sh/uv/) and Python 3.14** (pinned: `python3.14`,
  and the Python uv uses; `python3` stays Ubuntu's, which the app and the
  agents' scripts run on), with
  **[jev-rerank](https://github.com/anteloc/jev-rerank)** (pinned release,
  with its locked dependencies), which ranks text files or SQLite text
  fields against a question in plain language; it needs a `TYPESAFE_API_KEY`
  when it runs
- **poppler-utils** (`pdftotext`, …), **ripgrep** (`rg`) and **git**
- **The 3D player**, ldraw-player: Rust + WebAssembly (tools/player in the
  [ldraw.rs-astra](https://github.com/anteloc/ldraw.rs-astra) fork of
  ldraw.rs), added from a pinned release zip
- **A persistent virtual display** (Xvfb), started once by the entrypoint for
  the life of the container, since LeoCAD's render mode needs a real
  (virtual, here) display even from the CLI
- **A shared folder**, `/data`, bind-mounted from the host's `./data`: the
  model collection (`data/generated`), chat history (`data/chats`) and the
  agents' work folders (`data/output`)

## Layout

```
.
├── Dockerfile
├── entrypoint.sh          # starts Xvfb once, then execs the main process
├── docker-compose.yml     # runs the web app; you can log into the container any time
├── docker-compose.dev.yml # development overlay: live backend code + auto-reload
├── requirements.txt
├── leocad_render.py       # render_image() + a CLI — wrapper around leocad
├── example.py             # batch worker: makes missing snapshots + BOMs in data/generated/
├── models-annotated/      # baked into the image at /opt/models-annotated/
├── models-demo/           # demo models (+ .png, .csv, .md), baked in at /opt/models-demo/
├── scripts/               # command-line helpers, at /opt/scripts/ on the PATH (mpd2glb.sh, ...)
├── web/
│   ├── backend/           # FastAPI: chat API, agent loop (LiteLLM), tools, file routes
│   ├── frontend/          # React + Vite UI (built in a Docker build stage)
│   ├── xr/                # mixed-reality viewer: Vite + Meta's Immersive Web SDK (own build stage)
│   └── viewer/            # viewer.html (three.js 3D viewer), player.html (3D player)
├── vendor/                # ldraw-player-<version>.zip (+ .sha256): the 3D player, a local build for now
└── data/                  # mounted at /data (not baked in)
    ├── generated/         # the model collection, flat: car.mpd + car.png (snapshot) + car.csv (BOM), ...
    ├── chats/<chat>/      # one folder per chat: history, model references, renders
    └── output/<chat>/     # one work folder per chat, for the agents (not shown in the UI)
```

| Host | Container | |
|---|---|---|
| `./data/generated/` | `/data/generated/` | models (`.mpd`/`.ldr`/`.dat`) + same-named `.png` snapshots and `.csv` BOMs; drop your own models here |
| `./data/chats/` | `/data/chats/` | chat history, one folder per chat |
| `./data/output/` | `/data/output/` | agents' work folders (one per chat); also the CLI's default render folder |
| `./models-annotated/` | `/opt/models-annotated/` | baked in at build time (rebuild to update) |
| named volume `config` | `/config/` | LLM settings and API keys (not on the host, on purpose) |

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
docker build -t ldraw-astra-app .
# pin a specific stable release explicitly (check
# https://github.com/leozide/leocad/releases for available tags):
docker build --build-arg LEOCAD_TAG=v25.09 -t ldraw-astra-app .
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
docker compose exec ldraw-astra-app bash       # log in — repeat as often as you like
```

Inside the container:

```bash
python3 /app/leocad_render.py /opt/models-annotated/8303-1.mpd
#   -> /data/output/8303-1.png, i.e. ./data/output/8303-1.png on the host

python3 /app/leocad_render.py /opt/models-annotated/316-1.mpd /opt/models-annotated/854-1.mpd \
    --width 1920 --height 1080 --camera-angles 20 60
python3 /app/leocad_render.py /data/my-model.ldr -o /data/output/tests
python3 /app/leocad_render.py --help

python3 /app/example.py                   # make missing snapshots + BOMs in /data/generated
```

Open `./data/output/` on the host to look at the CLI's renders. When you're done:

```bash
docker compose down
```

### One-off runs

```bash
docker run --rm -it --init -v "$PWD/data:/data" ldraw-astra-app bash
docker run --rm --init -v "$PWD/data:/data" ldraw-astra-app python3 /app/example.py
docker compose run --rm ldraw-astra-app python3 /app/example.py
```

`example.py` makes, for every model in `data/generated`, whatever is missing
of its snapshot (`car.mpd` → `car.png`, from LeoCAD's home view) and its bill
of materials (`car.csv`, LeoCAD's CSV parts list) — the same thing the web
app's Models page does when you open it.

`--init` matters: the entrypoint runs Xvfb in the background *and* your main
process in the foreground, so you want Docker's built-in init to reap
zombies and forward signals correctly.

Raw `leocad` calls still work directly (no `--libpath` needed — see below):

```bash
docker run --rm --init -v "$PWD/data:/data" ldraw-astra-app \
    leocad /data/car.ldr -i /data/output/car.png -w 1280 -h 720 --camera-angles 30 40
```

## Web app

```bash
docker compose up -d --build
open http://localhost:8765                # port: LDRAW_ASTRA_WEB_PORT in .env
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
   parts, bad colours), publishes it to `data/generated` with a snapshot and —
   if the model accepts images — looks at the snapshot to fix problems. It can
   also run Python or shell in its work folder (e.g. to generate a model with
   a script); anything it writes into `data/generated` is published too.
3. **Snapshots** appear in the chat. Click one for the 3D viewer, or download
   the model (`.mpd`), a glTF version of it (`.glb`) or its bill of materials
   (**BOM**). The sidebar keeps the chat history with thumbnails.
4. **Models** shows everything in `data/generated` — from chats or copied in by
   hand — as "`name.mpd`, N parts", with the description from each file's
   title line (line 2 of an `.mpd`). When you open the page, models without a
   snapshot (`.png`, rendered from LeoCAD's home view) or BOM (`.csv`, LeoCAD's
   parts list, which also gives the part count) get them; delete either to
   have it regenerated. After them come the **demo models** that ship with the
   app (marked *Demo*); a model in `data/generated` with the same base name
   replaces a demo model, with all its files. A model with a Markdown file of
   the same base name (`atlas-crane.md` next to `atlas-crane.mpd`: the prompt
   that made it, say) gets an **Info** button that shows it. **Download all**
   zips all of it.
5. **3D view / 3D player** on each card open the model in the three.js viewer
   or in the player, which plays back how it's built; the window's header
   switches between the two. **VR** opens it in mixed reality on a Meta
   Quest 3 (see [Mixed reality](#mixed-reality-meta-quest-3)).
6. **`.glb`** (on each card and in the 3D viewer) converts the model with
   mpd2glb — uncompressed (`-c none`), real LEGO size in metres, LDraw
   metadata kept as custom properties on each node (readable in Blender,
   three.js editor, …) — and downloads it. Big models can take a minute; the
   result is cached until the model file changes.

Where things live:

| What | Where |
|---|---|
| Models | `data/generated/<name>.mpd` (chat models: `<name>-v<N>.mpd`, never overwritten) |
| Their snapshots and BOMs | `data/generated/<name>.png`, `data/generated/<name>.csv` — same base name, same folder |
| Notes on a model (Info) | `data/generated/<name>.md`, optional: Markdown, written by hand |
| Demo models | `models-demo/` in the repo (`/opt/models-demo/` in the image): each with its `.png`, `.csv` and optional `.md`, all made beforehand |
| A chat | `data/chats/<chat>/`: `chat.json` (title, model), `messages.jsonl` (history), `models.jsonl` (references to its models, e.g. `../../generated/red-car-v1.mpd`), `renders/` (extra renders shown in the chat) |
| A chat's work folder | `data/output/<chat>/`: the agents' notes (`NOTES.md`), plans, drafts, scripts (`.scripts/`) — never served by the web app |
| LLM settings, API keys | `/config` volume (`docker compose down -v` deletes it) |

**Switching models mid-chat.** Pick another model in the composer at any
time. The whole history is in the chat folder, and the agent keeps its plan
and progress in `NOTES.md` in the chat's work folder; every turn's system
prompt lists that folder, so the next model picks up where the last one left
off. Deleting a chat removes its chat and work folders; its models stay in
`data/generated`.

**The 3D viewer** is `/viewer/viewer.html?model=<url>` — e.g.
http://localhost:8765/viewer/viewer.html?model=/ref/8303-1.mpd for a
reference model. Rendering:

* **High** (the default): realistic plastic/metal/rubber/transparent
  materials, soft studio lighting, faint edge lines and a ground shadow. Its
  shadow is computed once per model rather than per frame, and its edges are
  one merged draw call, so it needs fewer draw calls than Normal.
* **Normal**: the fast outlined LDraw look.
* **Poly**: the bare triangles as a wireframe, in flat colours, with no
  lighting, textures or edge lines (very light colours are drawn a bit darker
  so they show on the light background).

And two ways to move the camera, the same as in the 3D player:

* **Inspect**: drag to rotate, Shift+drag to pan, scroll to zoom towards the
  pointer. Zooming doesn't stop at the model: keep scrolling and the camera
  flies in and through walls, to look around inside buildings.
* **Walk**: first person, like a game. Click and the mouse looks around (Esc
  frees the pointer; dragging works too); **W A S D** move, **E / Q** go up and
  down, **Shift** runs, scrolling flies along the pointer. Back in Inspect, the
  camera orbits a point just ahead of where you walked to.

Nothing stops the camera at walls in either mode; the reset-view button
brings back the whole model. It is library.ldraw.org's viewer
([ldraworg-library](https://github.com/ldraw-org/ldraworg-library), MIT, built
on [buildinginstructions.js](https://github.com/LasseD/buildinginstructions.js),
Unlicense), vendored into the image at a pinned commit (`LDRAWORG_REF`), with
parts served from the baked-in library instead of ldraw.org, and a perspective
camera instead of its orthographic one (which can't go inside a model).

**The 3D player** is `/viewer/player.html?model=<url>` — e.g.
http://localhost:8765/viewer/player.html?model=/ref/8303-1.mpd. Parts drop
into place step by step while the camera slowly turns (in Inspect); that's
what **play** does, and **pause** stops both. **|◀ / ▶|** jump to the previous / next step,
and the time slider is cut into the steps like the chapters of a video (hover
for the step number). Keys: Space play/pause, ←/→ previous/next step,
Home/End. A build takes about a minute at 1×, whatever its size (small models
keep their natural pace), and the speed menu goes from 0.25× to 4×. The camera
has the viewer's **Inspect** and **Walk** modes, at any time, also while
paused (in Walk, E / Q go up and down: Space stays play/pause). The reset-view
button (bottom right) brings back the whole model. It renders with ldraw.rs's own renderer (wgpu):
WebGPU where the browser has it, WebGL2 otherwise.

It's ldraw-player, `tools/player` in the
[ldraw.rs-astra](https://github.com/anteloc/ldraw.rs-astra) fork, which
adds it next to the ldraw.rs demo viewer (unchanged); see its README for the
JavaScript API. The image takes `ldraw-player-<version>.zip`, pinned by
version and SHA-256 (`LDRAW_PLAYER_VERSION`, `LDRAW_PLAYER_SHA256` in the
Dockerfile), from `vendor/` for now: a local build (`VERSION=0.8.1
tools/player/build.sh` in the fork), because the v0.8.0 release on
[GitHub](https://github.com/anteloc/ldraw.rs-astra/releases) doesn't start in
any browser. Once a fixed release is published, the Dockerfile's `COPY` goes
back to the commented `curl` line next to it.

While working on the player itself, `docker-compose.dev.yml` can mount your
local build over the baked-in one (see the commented line there).

### Mixed reality (Meta Quest 3)

**VR** (on each model card, and in the viewer window's header) opens
`/xr/?model=<url>`: the model in passthrough mixed reality, through WebXR in
the Quest browser. It shows the model's size and draw calls, then **Enter MR**.

**Reaching the app from the Quest.** WebXR only runs on secure pages: HTTPS,
or `localhost`. A plain `http://<your computer's IP>:8765` page loads, but
**Enter MR** stays off (the page says why and links to the HTTPS address).
Two ways:

* **HTTPS over Wi-Fi:** open `https://<your computer's IP>:8443` in the Quest
  browser (the app's HTTPS port, `LDRAW_ASTRA_WEB_HTTPS_PORT`). The certificate is
  self-signed, made once and kept in the `config` volume: the first time, the
  browser warns, choose Advanced → Proceed. This needs the ports reachable
  from the network, which also exposes the app (it has no login) to
  everyone on it.
* **adb, with the app on localhost only:** with developer mode on and the
  Quest connected over USB (or wireless adb):

  ```bash
  adb reverse tcp:8765 tcp:8765        # the Quest's localhost:8765 -> this machine's
  # then, in the Quest browser: http://localhost:8765 -> a model card -> VR -> Enter MR
  ```

**In the headset:**

* Both hands work the same, with the **trigger** (or a pinch); each has a
  laser, so you see what it points at.
* Point at a table or the floor and press: the model is put there (a ring
  shows the spot). At first it stands in front of you at tabletop size.
* Point at the model and hold: move and turn it; hold it with **both hands**
  and pull apart or together: scale it (evenly, around where you hold it).
* The menu follows your view. It's open when you enter, closes once you've
  put the model somewhere or picked a size, and **B** or **Y** (the upper
  buttons) show or hide it: **Real size** (actual LEGO size), **Tabletop**
  (60 cm), **Walk-in** (minifig scale, ×45, on the floor: walk in, or use the
  thumbsticks), **Stats** (frame rate, frame time, draw calls, triangles, and
  any shader error; also logged to the console every 5 s, readable with
  `chrome://inspect` over adb), **Exit**.

**Why it's fast.** The model is loaded as the same `.glb` as above, then its
thousands of parts are batched into at most 4 draw calls (three.js
`BatchedMesh`: opaque/transparent × normal/mirrored parts), with each unique
part geometry stored once and made indexed (e.g. the cathedral: 5,394 parts,
37 unique geometries, 2 draw calls; its vertices shrink from 80,646 to 27,247).
It runs on Meta's [Immersive Web SDK](https://iwsdk.dev) (three.js with
multiview: both eyes in one draw), with fixed foveation and a 72 Hz target.
Parts out of view aren't drawn (per-part culling, which pays off once you
walk into a model). Left out on purpose: edge lines (1 px lines alias in a
headset and cost up to a third of the vertices), PBR materials, environment
maps and shadows (instead: glossy Blinn-Phong plastic, lit by the sky, a key
light and a headlight that follows your view). Page options: `&stats=1`,
`&fps=90`, `&scale=0.8` (render resolution), `&light=1.3` (brighter, or
`0.8` darker), `&emulate=quest3` (an emulated headset, to try it on a
computer).

Studs are about 80% of the triangles (the cathedral: 2.39M, 0.47M without);
if a large model doesn't hold its frame rate, the next step is to draw studs
separately and drop the ones covered by other parts.

**mpd2glb by hand**, from a `docker compose exec ldraw-astra-app bash` shell:

```bash
mpd2glb.sh -c none -l /opt/ldraw/ldraw -o /data/output/cathedral.glb /data/generated/cathedral.mpd
mpd2glb.sh --help               # draco/meshopt compression, colour remapping, ...
```

Always through `scripts/mpd2glb.sh` (the web app too), so how mpd2glb runs can
change in one place. Versions are pinned as build args (`BUN_VERSION`,
`MPD2GLB_VERSION`, and for the other tools `UV_VERSION`, `PYTHON_VERSION`,
`JEV_RERANK_VERSION`, `LDRAW_PLAYER_VERSION`, each download with its SHA-256);
bump them and rebuild to upgrade. Bun rather than Node.js:
measured on this image it converts 2.7–3.7× faster on larger models, with
byte-identical output (Deno was no faster than Node). It's Bun's *baseline*
x64 build, since the emulated CPU on Apple Silicon has no AVX2.

**Security.** This is a local, single-user tool:

* The port is bound to `127.0.0.1` only. There is no login, and anyone who
  can reach it can spend your API keys and run code in the container.
* Agent code runs as the unprivileged `agent` user with a scrubbed environment
  and CPU/file-size limits. It can't read `/config` (API keys) and its tools
  only reach `data/generated` and its own work folder, but code it runs can
  write anywhere in `/data` on Docker Desktop (Mac/Windows bind mounts don't
  enforce ownership) — including `data/chats` — and it has network access.
* For stronger isolation, move `web/backend/sandbox.py`'s execution into a
  separate container with only `data/generated` mounted and no network.

### Developing the web app

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d   # backend from your checkout, auto-reload
cd web/frontend && npm install && npm run dev                          # UI with hot reload: http://localhost:5173
cd web/xr && npm install && npm run dev      # mixed-reality viewer: /xr/?model=...&emulate=quest3 (next free port)
cd web/xr && npm test                        # its batching tests

# backend tests (inside the container: they use LeoCAD and the real library)
docker compose exec ldraw-astra-app bash -c \
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

Full reference: `docker run --rm ldraw-astra-app leocad --help`, or
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
