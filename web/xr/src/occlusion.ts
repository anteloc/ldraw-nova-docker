// Real things in front of the model hide it, through WebXR depth sensing (the
// headset's live depth map) and IWSDK's DepthSensingSystem. It's for safety:
// scaled up, the model fills the room, and the chair or table in front of it
// must stay in view, not get walked into.
//
// Hard occlusion by default: one depth sample per pixel, no blur and no extra
// pass, the cheapest (edges are a little jagged, around fingers say).
// ?occlusion=soft or minmax to compare them, ?occlusion=off for none.
import { DepthOccludable, DepthSensingSystem, type Entity, OcclusionShadersMode, type World } from "@iwsdk/core";

const MODES = {
  hard: OcclusionShadersMode.HardOcclusion,
  soft: OcclusionShadersMode.SoftOcclusion,
  minmax: OcclusionShadersMode.MinMaxSoftOcclusion,
};
export type OcclusionMode = keyof typeof MODES | "off";

/** The `?occlusion=` page option; hard unless it names another mode, or turns it off. */
export function occlusionMode(param: string | null): OcclusionMode {
  if (param === "off" || param === "0" || param === "false") return "off";
  return param && param in MODES ? (param as OcclusionMode) : "hard";
}

/**
 * The session feature, optional: without depth (another headset, or the
 * emulator), mixed reality starts anyway, unoccluded. Depth stays on the GPU.
 */
export const DEPTH_SENSING = { usage: "gpu-optimized", format: "float32" } as const;

interface Shader {
  vertexShader: string;
}

/** Registers the depth system, once the world is created (unless off). */
export function enableOcclusion(world: World, mode: OcclusionMode) {
  if (mode === "off") return;
  useProjectedDepth();
  world.registerSystem(DepthSensingSystem, { configData: { enableOcclusion: true, enableDepthTexture: true } });
}

/** Lets real things hide `entity` (the model: not the menu, lasers or tags). */
export function occlude(entity: Entity, mode: OcclusionMode) {
  if (mode !== "off") entity.addComponent(DepthOccludable, { mode: MODES[mode] });
}

// IWSDK compares the real depth with the fragment's, which it takes from the
// raw vertex position: wrong for a BatchedMesh (and instanced meshes), whose
// parts are put in place by a matrix per part. Each part would count as if it
// sat at its own origin. Use the position three.js has already projected
// (mvPosition: batching, instancing, morphs and skinning applied); it's in
// scope where IWSDK adds its line, after <fog_vertex>.
let patched = false;
function useProjectedDepth() {
  if (patched) return;
  patched = true;
  const system = DepthSensingSystem as unknown as { addOcclusionToShader(shader: Shader): void };
  const add = system.addOcclusionToShader.bind(system);
  system.addOcclusionToShader = (shader) => {
    add(shader);
    const raw = "occlusion_view_pos = modelViewMatrix * vec4(position, 1.0);";
    if (shader.vertexShader.includes(raw)) {
      shader.vertexShader = shader.vertexShader.replace(raw, "occlusion_view_pos = mvPosition;");
    } else if (!shader.vertexShader.includes("occlusion_view_pos = mvPosition;")) {
      console.warn("[xr] IWSDK's occlusion shader changed: real-world occlusion of the model may be wrong");
    }
  };
}
