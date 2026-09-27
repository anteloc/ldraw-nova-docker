// LDraw mixed-reality viewer: /xr/?model=<url>[&parts=N][&stats=1][&fps=72|90][&scale=1][&light=1][&emulate=quest3]
//
// Loads the model as GLB (converted by the backend with mpd2glb), batches it
// into a few draw calls (batching.ts) and shows it with Meta's Immersive Web
// SDK: passthrough mixed reality on a Quest 3 (immersive-ar), VR elsewhere.
import {
  Color,
  createSystem,
  DirectionalLight,
  FollowBehavior,
  Follower,
  HemisphereLight,
  InputComponent,
  NeutralToneMapping,
  PanelDocument,
  PanelUI,
  RayInteractable,
  ReferenceSpaceType,
  SessionMode,
  type UIKitDocument,
  VisibilityState,
  World,
} from "@iwsdk/core";
import { fixShaderExtensions } from "./batching";
import { formatSample, PerfMeter, type Sample } from "./hud";
import { createFloor, PlacedModel, PlacementSystem } from "./interaction";
import { loadModel } from "./model";

const params = new URLSearchParams(location.search);
const $ = (id: string) => document.getElementById(id)!;
const statusEl = $("status");
const statsEl = $("stats");
const enter = $("enter") as HTMLButtonElement;
const BACKGROUND = new Color(0xf2f2f2);
const VR_BACKGROUND = new Color(0x2a2a2e);

const setStatus = (text: string, error = false) => {
  statusEl.textContent = text;
  statusEl.classList.toggle("error", error);
};
const plural = (n: number, word: string) => `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
const millions = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : `${Math.round(n / 1e3)}K`);

/** An emulated Quest 3 (IWER), for trying and testing this page without a headset. */
async function installEmulator() {
  const { XRDevice, metaQuest3 } = await import("iwer");
  const device = new XRDevice(metaQuest3);
  device.installRuntime({ forceInstall: true });
  (window as unknown as { xrDevice: unknown }).xrDevice = device; // tests drive it
}

/** HTTPS port of the app (docker-compose.yml: LDRAW_ASTRA_WEB_HTTPS_PORT). */
const HTTPS_PORT = 8443;

/** The session mode to offer, or why none can be. */
async function xrSupport(): Promise<{ mode: SessionMode | null; why?: string }> {
  // Browsers only expose WebXR on secure pages: HTTPS, or localhost.
  if (!window.isSecureContext) return { mode: null, why: "insecure" };
  const xr = navigator.xr;
  if (!xr) return { mode: null, why: "This browser has no WebXR: open this page in the Meta Quest browser." };
  const supported = (mode: XRSessionMode) => xr.isSessionSupported(mode).catch(() => false);
  if (await supported("immersive-ar")) return { mode: SessionMode.ImmersiveAR };
  if (await supported("immersive-vr")) return { mode: SessionMode.ImmersiveVR };
  return { mode: null, why: "No mixed or virtual reality here: open this page on a Meta Quest 3." };
}

/** Why Enter is off, with the way out: the same page over HTTPS. */
function explainNoXR(why: string) {
  const hint = $("xr-hint");
  if (why === "insecure") {
    const url = `https://${location.hostname}:${HTTPS_PORT}${location.pathname}${location.search}`;
    hint.append(
      "Mixed reality needs a secure page (HTTPS or localhost), and this one is plain http. Open it over HTTPS: ",
      Object.assign(document.createElement("a"), { href: url, textContent: url }),
      " (the first time, the browser warns about the certificate: Advanced → Proceed).",
    );
  } else {
    hint.textContent = why;
  }
  hint.hidden = false;
}

/**
 * Wires the menu's buttons (public/ui/menu.uikitml) once IWSDK has loaded it;
 * B or Y (the upper face buttons) toggle the menu.
 */
class MenuSystem extends createSystem({ panels: { required: [PanelUI, PanelDocument] } }) {
  static actions: Record<string, () => void> = {};
  static document: UIKitDocument | null = null;
  static toggle = () => {};

  init() {
    this.queries.panels.subscribe("qualify", (entity) => {
      const doc = entity.getValue(PanelDocument, "document") as UIKitDocument;
      doc.setTargetDimensions(0.36, 0.36); // metres: big enough to aim at comfortably
      // The menu can end up inside the model (it's grabbable by ray, from its
      // bounds): draw it on top, and let it win when a ray hits both.
      doc.rootElement.setProperties({ depthTest: false, renderOrder: 1000, pointerEventsOrder: 1 });
      for (const [id, action] of Object.entries(MenuSystem.actions)) {
        doc.getElementById(id)?.addEventListener("click", action);
      }
      MenuSystem.document = doc;
    });
  }

  update() {
    const { left, right } = this.input.xr.gamepads;
    if (left?.getButtonDown(InputComponent.Y_Button) || right?.getButtonDown(InputComponent.B_Button)) {
      MenuSystem.toggle();
    }
  }
}

async function main() {
  const modelUrl = params.get("model");
  if (!modelUrl) {
    setStatus("No model given: add ?model=<url of an .ldr/.mpd file>", true);
    return;
  }
  const fileName = decodeURIComponent(modelUrl.split("/").pop()!.split("?")[0]);
  $("file").textContent = fileName;
  document.title = `${fileName} · LDraw MR`;
  const knownParts = Number(params.get("parts"));
  if (knownParts > 0) $("parts").textContent = `, ${plural(knownParts, "part")}`;

  if (params.get("emulate")) await installEmulator();
  const { mode, why } = await xrSupport();
  if (why) explainNoXR(why);
  const targetFps = Number(params.get("fps")) || 72;

  const world = await World.create($("scene-container"), {
    xr: {
      sessionMode: mode ?? SessionMode.ImmersiveAR,
      referenceSpace: ReferenceSpaceType.LocalFloor,
      features: { handTracking: true, hitTest: true },
      offer: "none",
    },
    // near 1 cm: real-size models can be looked at from up close, and from inside
    render: { fov: 50, near: 0.01, far: 500, camera: { position: [0, 1.35, 0.55], lookAt: [0, 0.95, -0.45] } },
    features: { grabbing: true, environmentRaycast: true, locomotion: { enableJumping: false }, spatialUI: true },
  });
  fixShaderExtensions(world.renderer.getContext() as WebGL2RenderingContext);
  let showStats = Boolean(params.get("stats"));
  const setStats = (show: boolean) => {
    showStats = show;
    MenuSystem.document?.getElementById("stats")?.setProperties({ display: show ? "flex" : "none" });
  };
  // A shader that doesn't compile draws nothing, and in the headset nobody sees
  // the console: show it in the menu's stats (and the page's).
  let shaderError = "";
  world.renderer.debug.onShaderError = (gl, program, vertexShader, fragmentShader) => {
    const log = [gl.getProgramInfoLog(program), gl.getShaderInfoLog(vertexShader), gl.getShaderInfoLog(fragmentShader)]
      .map((text) => text?.trim())
      .filter(Boolean)
      .join("\n");
    console.error("[xr] shader error:", log);
    shaderError ||= `Shader error: ${log.split("\n").find((line) => /error/i.test(line)) ?? log.split("\n")[0]}`;
    setStats(true);
  };
  // Walkable floor first: locomotion has gravity, and the player would fall
  // through while the model loads.
  createFloor(world);
  world.renderer.xr.setFramebufferScaleFactor(Number(params.get("scale")) || 1);
  world.scene.background = BACKGROUND;
  // Light: sky and ground, a key light from above, and a headlight (on the
  // camera) so whatever side you look at is lit and the plastic's highlights
  // follow you. Neutral tone mapping keeps pale bricks from clipping to flat
  // white (the menu opts out). ?light= scales it all, to tune in the headset.
  const light = Number(params.get("light")) || 1;
  world.renderer.toneMapping = NeutralToneMapping;
  world.scene.add(new HemisphereLight(0xffffff, 0x8a8074, 2.2 * light));
  const key = new DirectionalLight(0xffffff, 2.2 * light);
  key.position.set(1, 3, 2);
  world.scene.add(key);
  const headlight = new DirectionalLight(0xffffff, 1.0 * light);
  headlight.target.position.set(0, -0.3, -1); // ahead, a little down
  world.camera.add(headlight, headlight.target);
  const meter = new PerfMeter(world);

  let loaded;
  try {
    loaded = await loadModel(modelUrl, (text) => setStatus(text));
  } catch (e) {
    setStatus((e as Error).message, true);
    return;
  }
  const { model, times } = loaded;
  const { stats } = model;
  if (!(knownParts > 0)) $("parts").textContent = `, ${plural(stats.parts, "part")}`;

  const placed = new PlacedModel(world, model);
  const preview = () => {
    placed.tabletop();
    placed.holder.position.set(0, 0.75, -0.45);
    placed.faceTowards(world.camera.position);
  };
  preview();
  PlacementSystem.model = placed;
  world.registerSystem(PlacementSystem);

  // The in-headset menu, following the view (lower left). Open when you enter,
  // closed once the model is in place (so it's out of the way of the view and
  // the lasers), B or Y bring it back.
  MenuSystem.actions = {
    "real-size": () => (placed.realSize(), showMenu(false)),
    tabletop: () => (placed.tabletop(), showMenu(false)),
    "walk-in": () => (placed.walkIn(), showMenu(false)),
    "stats-button": () => setStats(!showStats),
    exit: () => world.exitXR(),
  };
  world.registerSystem(MenuSystem);
  const menu = world.createTransformEntity(undefined, { persistent: true });
  menu.addComponent(PanelUI, { config: `${import.meta.env.BASE_URL}ui/menu.uikitml` });
  // It stays put while it's within 45° of where you look (it sits about 25°
  // off, lower left), so it holds still while you aim at it; it catches up
  // once you turn away.
  menu.addComponent(Follower, {
    target: world.player.head,
    offsetPosition: [-0.22, -0.2, -0.6],
    behavior: FollowBehavior.FaceTarget,
    maxAngle: 45,
    speed: 2,
  });
  let menuOpen = false;
  function showMenu(open: boolean) {
    menuOpen = open;
    if (menu.object3D) menu.object3D.visible = open;
    // Hidden, it must not stop the lasers either: rays only test ray interactables.
    if (open && !menu.hasComponent(RayInteractable)) menu.addComponent(RayInteractable);
    if (!open && menu.hasComponent(RayInteractable)) menu.removeComponent(RayInteractable);
    if (open) menu.setValue(Follower, "needsPositionSync", true); // in front of you, not where it was
  }
  showMenu(false);
  MenuSystem.toggle = () => world.session && showMenu(!menuOpen);
  PlacementSystem.onPlaced = () => showMenu(false);

  world.visibilityState.subscribe((state) => {
    const immersive = state !== VisibilityState.NonImmersive;
    if (!immersive) {
      showMenu(false);
      world.scene.background = BACKGROUND;
      preview();
    }
  });
  world.renderer.xr.addEventListener("sessionstart", () => {
    const xr = world.renderer.xr;
    xr.setFoveation(1); // fixed foveated rendering: full detail only where you look
    const session = xr.getSession() as (XRSession & {
      supportedFrameRates?: Float32Array;
      updateTargetFrameRate?: (rate: number) => Promise<void>;
    }) | null;
    if (session?.supportedFrameRates?.includes(targetFps)) session.updateTargetFrameRate?.(targetFps).catch(() => {});
    world.scene.background = mode === SessionMode.ImmersiveVR ? VR_BACKGROUND : null; // passthrough in MR
    PlacementSystem.placeAfter = 3; // a few frames, so the head pose is real
    showMenu(true);
  });

  // Numbers: page, menu (Stats), and the console every 5 s while immersive.
  let logged = 0;
  setInterval(() => {
    const sample: Sample | null = meter.latest;
    if (!sample) return;
    const text = [shaderError, formatSample(sample)].filter(Boolean).join(" · ");
    if (showStats) statsEl.textContent = text;
    // the panel's font has no "·"
    if (showStats) {
      MenuSystem.document?.getElementById("stats")?.setProperties({ display: "flex", text: text.replaceAll(" · ", " | ") });
    }
    if (world.session && performance.now() - logged > 5000) {
      logged = performance.now();
      console.info(`[xr-stats] ${fileName}: ${text}`);
    }
  }, 500);

  const loadedIn = times.fetch + times.parse + times.batch;
  setStatus(
    `${plural(stats.parts, "part")} · ${stats.batches} draw call${stats.batches === 1 ? "" : "s"} · ` +
      `${millions(stats.triangles)} triangles · ready in ${loadedIn.toFixed(1)} s`,
  );
  enter.textContent = mode === SessionMode.ImmersiveVR ? "Enter VR" : "Enter MR";
  enter.disabled = !mode;
  enter.addEventListener("click", () => world.launchXR({ sessionMode: mode ?? SessionMode.ImmersiveAR }));
  Object.assign(window, { xrApp: { world, model, placed, meter, menu: () => MenuSystem.document } }); // for tests and the console
}

main().catch((e) => setStatus(`Could not start: ${(e as Error).message}`, true));
