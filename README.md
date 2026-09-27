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
- **The demo models** from `models-demo/`, baked into the image at
  `/opt/models-demo/` and shown on the Models page
- **[mpd2glb](https://github.com/anteloc/mpd2glb)** (pinned release, run with
  a pinned [Bun](https://bun.com/) through `scripts/mpd2glb.sh`), which converts LDraw models to glTF `.glb` while keeping
  the LDraw metadata (descriptions, part files, colours, building steps) on
  every node
- **`scripts/`**, the whole folder, at `/opt/scripts/` and on the `PATH`
  (the agents' too): whatever is in it runs from anywhere in the container, by
  name — e.g. `mpd2glb.sh` (the way to run mpd2glb, whatever runs it
  underneath) and `ldraw-render-steps.sh` (a picture per building step, with
  LeoCAD)
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
├── models-demo/           # demo models (+ .png, .csv, .md), baked in at /opt/models-demo/
├── scripts/               # command-line helpers, baked in at /opt/scripts/: all on the PATH
├── web/
│   ├── backend/           # FastAPI: chat API, agent loop (LiteLLM), tools, file routes
│   ├── frontend/          # React + Vite UI (built in a Docker build stage)
│   ├── xr/                # mixed-reality viewer: Vite + Meta's Immersive Web SDK (own build stage)
│   └── viewer/            # viewer.html (three.js 3D viewer), player.html (3D player)
├── vendor/                # ldraw-player-<version>.zip (+ .sha256): the 3D player, a local build for now
└── data/                  # mounted at /data (not baked in)
    ├── generated/         # the model collection, flat: car.mpd + car.png (snapshot) + car.csv (BOM), ...
    ├── chats/<chat>/      # one folder per chat: history, model references, renders
    └── output/<chat>/     # editable sources, plans, reports and previews per chat
```

| Host | Container | |
|---|---|---|
| `./data/generated/` | `/data/generated/` | models (`.mpd`/`.ldr`/`.dat`) + same-named `.png` snapshots and `.csv` BOMs; drop your own models here |
| `./data/chats/` | `/data/chats/` | chat history, one folder per chat |
| `./data/output/` | `/data/output/` | agents' work folders (one per chat); also the CLI's default render folder |
| `./models-demo/` | `/opt/models-demo/` | demo models, baked in at build time (rebuild to update) |
| `./scripts/` | `/opt/scripts/` | command-line helpers, on the `PATH`; baked in at build time (rebuild to update) |
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
docker build --build-context astra=../ldraw-astra -t ldraw-astra-app .
# pin a specific stable release explicitly (check
# https://github.com/leozide/leocad/releases for available tags):
docker build --build-context astra=../ldraw-astra --build-arg LEOCAD_TAG=v25.09 -t ldraw-astra-app .
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
python3 /app/leocad_render.py /opt/models-demo/copper-bean.mpd
#   -> /data/output/copper-bean.png, i.e. ./data/output/copper-bean.png on the host

python3 /app/leocad_render.py /opt/models-demo/cathedral.mpd /opt/models-demo/sakura-garden.mpd \
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

1. **Settings → Provider accounts.** Click **Sign in with ChatGPT** or
   **Sign in with Claude**. Complete the provider's login in your browser.
   ChatGPT uses browser authorization and returns automatically through
   `http://localhost:1455`; complete this on the computer running Docker.
   No device code, account security change, or terminal command is required
   for this default flow. The callback is bound only to host loopback; Docker
   relays it to the official OpenAI runtime's internal callback listener.
   Keep host port 1455 free while running this compose stack. Claude opens its
   authorization page on `claude.com` and displays a code after sign-in. Copy
   the full code into **Claude authorization code** in this app and click
   **Complete login**. No terminal command or additional callback port is needed.
   Settings polls until the provider confirms the login; you can cancel,
   retry, or disconnect. For a browser on a different machine, expand
   **Signing in from another computer?** and use the optional device flow.
   That fallback requires enabling device code sign-in in ChatGPT Security
   Settings first. Start it again in this app afterwards; you do not need
   to run the terminal command mentioned on OpenAI's device page.
   An eligible subscription and model entitlement
   are required; signing into the provider website alone does not connect this app.

   **Settings → Environment variables.** Click **Add** for a row with a name
   and value, then **Save environment variables**. Saved variables override
   the backend's inherited Docker / `.env` values and become available to new
   requests immediately. For example, save `OPENROUTER_LDRAW_ASTRA_API_KEY`
   here and existing models using `os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY`
   automatically use the saved key. Nested parameter references work too.
   Empty values override inherited values with empty text. Removing a row
   restores its inherited value, or removes the variable if none existed.

   Values persist privately in `/config/environment.json` (0600) and are
   loaded before backend configuration and provider libraries at startup.
   Saved values are hidden in the editor; select a value field to replace or
   clear it. API responses include names and saved-value indicators only.
   These are backend environment overrides: settings read only at startup
   take effect on backend restart, and Docker ports and other container
   settings remain managed by Compose. Tool subprocesses keep their restricted
   environment. Only `TYPESAFE_API_KEY` is deliberately passed to builder commands for Jev;
   provider API keys and browser credentials remain private. The TypeSafe value is
   redacted from command logs and uses the Settings override immediately.

   For **OpenRouter**, use **Add model → OpenRouter** or select an OpenRouter
   model preset. The presets include GPT-6 Astra, Sol and Luna, GPT-5.6 Terra,
   Claude Opus 5.5 and 5, Sonnet 5, and Haiku 4.5 with their OpenRouter model
   IDs, vision/tool capabilities, context budgets and supported effort levels.
   You can also enter another `openrouter/vendor/model` ID. OpenRouter uses API
   key authentication and its own billing, separate from browser subscriptions.

   The OpenRouter preset uses `os.environ/OPENROUTER_LDRAW_ASTRA_API_KEY`.
   Set it in **Environment variables** above for immediate updates, or let
   Docker Compose pass it from the host shell or `.env`. Changes to those
   inherited sources require `docker compose up -d` to recreate the container;
   a saved Settings override still takes precedence. The key is excluded from tool
   subprocesses and only its environment reference appears in model exports.
   Alternatively, paste a key in the API key field; it is stored privately in
   `/config` and masked in API responses. Leave the API base URL empty to use
   OpenRouter's standard endpoint, then click **Test** beside the saved model.

   **Settings → Add model.** Choose a model preset and **Browser login**, or
   choose **API key** and enter your provider key. You can also type any LiteLLM model string
   (`anthropic/claude-sonnet-5`, `openai/<model>`, `gemini/<model>`,
   `ollama_chat/<model>` with API base `http://host.docker.internal:11434`,
   any OpenAI-compatible server, …), an API key, and optionally extra LiteLLM
   parameters. **Test** sends a small request (Claude browser entries check login
   readiness; send a chat to test model access). Keys can also stay out of
   the UI: put `ANTHROPIC_API_KEY=...` in a `.env` file next to
   `docker-compose.yml` and enter `os.environ/ANTHROPIC_API_KEY` as the key.
   Existing LiteLLM proxy `model_list` YAML can be imported.
2. **Chat.** Ask for a model. The agent follows the standalone `ldraw-astra`
   instructions, studies references, builds editable plans/modules, validates
   geometry, renders and opens images for visual review. `publish_model`
   preserves the MPD and adds the same interactive model card used on Models:
   3D view, step player, VR and downloads. Validation failures remain visible;
   successful checks do not prove physical buildability. Editable sources,
   attribution, check reports, BOM comparisons and reviews stay under the
   chat's output folder and can be linked for download.

   Long builds show the current activity, elapsed time, command output and
   progress summaries. Reloading reconnects to the active command and its
   recent output. Stop terminates the running process group. Commands have a
   30-minute maximum; a turn permits up to 150 model/tool rounds. At that limit,
   send a message to continue from the saved work and `NOTES.md`.
   The composer offers **Agent**, **Plan** (read-only inspection), and **Chat**
   (no tools). **Ask before changes** is the default: approve or deny each write,
   render, or command in the chat. **Full access (container)** skips those prompts
   while retaining the unprivileged tool runner; it does not grant host/root access.
   **Read only** blocks all mutating tools. Approvals expire after ten minutes;
   Stop cancels pending approvals and running work. Reloading restores pending
   approval cards while the backend remains running.

   Effort choices follow the selected model's documented capabilities. Context
   budget limits the history sent on a turn, preserving complete tool exchanges
   and the latest user request; older turns and completed tool rounds may be omitted,
   with current hand-over notes retained, but saved history stays
   intact. It does not enlarge the provider's context window. Attach up to four
   PNG/JPEG/WebP images (5 MB each, 12 MB total) for models with vision.
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
| A chat's work folder | `data/output/<chat>/`: the agents' notes (`NOTES.md`), plans, drafts, scripts (`generators/`); explicit artifact downloads are available in chat |
| LLM settings, API keys, browser sessions | `/config` volume (`docker compose down -v` deletes it); tokens under `/config/browser/{openai,anthropic}` |

**Switching models mid-chat.** Pick another model in the composer at any
time. The whole history is in the chat folder, and the agent keeps its plan
and progress in `NOTES.md` in the chat's work folder; every turn's system
prompt lists that folder, so the next model picks up where the last one left
off. Deleting a chat removes its chat and work folders; its models stay in
`data/generated`.

**Provider adapters and model availability.** API-key inference uses LiteLLM.
ChatGPT browser authorization uses the pinned official
[OpenAI app-server login protocol](https://learn.chatgpt.com/docs/app-server).
It owns OAuth state and PKCE verification; its session is then imported into
LiteLLM's protected cache. The temporary OpenAI credential file is removed so
only LiteLLM refreshes the session. ChatGPT inference uses LiteLLM's
[subscription provider](https://docs.litellm.ai/docs/providers/chatgpt), including
token refresh. GPT-6 API calls are explicitly bridged to Responses for function
calling. Claude browser sessions use the pinned official
[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python) and its bundled
Claude Code login. That adapter reconstructs the shared conversation each turn
and exposes only this app's tools through an in-process MCP server. Both adapters
use the same permission gate and container tool runner. This MVP does not expose
the complete Codex/Claude Code plugin or agent ecosystem.

Presets verified on 2026-09-27 include GPT-6 Astra, Sol and Luna, GPT-5.6 Terra,
Claude Opus 5.5 and 5, Sonnet 5, and Haiku 4.5. The
[OpenAI catalog](https://developers.openai.com/api/docs/guides/latest-model) has
no GPT-6 Terra, and the
[Claude catalog](https://platform.claude.com/docs/en/models/overview) still lists
Haiku 4.5 as the released Haiku. Future IDs can be entered manually; unknown
models do not receive guessed effort/context controls. Update `model_catalog.py`
as capabilities become documented. Presets describe capabilities, not a guarantee
that your account can access a model.

The app remains a single-user service on the configured host/LAN ports. Its
provider connections are shared by everyone who can reach it. Restrict access
to trusted users; browser cross-origin API requests are rejected. OAuth tokens
and API keys remain in the root-only config volume, outside tool workspaces;
disconnecting ChatGPT deletes the local session (revoke account-wide access in
the provider's account settings if needed). Login subprocesses expire after
15 minutes and are stopped on server shutdown. Backend restart ends active turns
and pending approvals; the conversation history remains available.

**The 3D viewer** is `/viewer/viewer.html?model=<url>` — e.g.
http://localhost:8765/viewer/viewer.html?model=/demo/copper-bean.mpd for a
demo model. Rendering:

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
http://localhost:8765/viewer/player.html?model=/demo/copper-bean.mpd. Parts drop
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
  can read the toolkit resources and generated models and write its own work folder.
  Builder processes receive the configured TypeSafe key for Jev (other provider
  secrets are excluded). Code it runs can
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

### Developing the standalone builder

Keep `ldraw-astra/` and `ldraw-astra-docker/` beside each other. Compose passes
`../ldraw-astra` as a named build context. To incorporate any sibling changes:

```bash
docker compose up -d --build
```

The image installs the sibling's locked dependencies in its own Linux virtualenv
and copies its code, instructions, documentation, examples, database, categories
and connection metadata. It excludes the sibling's output, host virtualenv,
cache and private configuration. Nothing is written to the sibling checkout.
The standalone project requires no Docker files or awareness of this app.

For live edits, use Compose Watch with the development configuration:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --watch
```

Watch syncs builder files into `/opt/ldraw-astra`; changes to its dependency
manifest/lock rebuild the image. Existing long-running commands finish with
the code they loaded; new commands load changes. Rebuilds/restarts interrupt
active turns, so finish or stop them first.

`/opt/ldraw-astra/output` maps to `/data/output` (`./data/output` on the host).
Each chat receives a repository-shaped working directory whose `output/` maps
to `/data/output/<chat-id>`. The source repository and reference resources stay
shared and read-only to tool processes; its derived `.cache` is writable and
rebuildable. Commands run in the toolkit's Python environment, so its `ldraw`
package cannot collide with the web app's older parser.

Save `TYPESAFE_API_KEY` in **Settings → Environment variables**. Agents follow
the sibling's bounded live availability check before semantic discovery, then
explicitly use offline FTS if Jev is unavailable. Builds and validation also
work without a TypeSafe key.

The container-specific adapter is `web/backend/toolkit.py`; app tools are in
`web/backend/tools.py`. `web/backend/prompts/system.md` adds paths, progress
and publication instructions to the full sibling `instructions.md`, loaded
fresh each model round. LEGO construction rules remain owned by the sibling.

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
