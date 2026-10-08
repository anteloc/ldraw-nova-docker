// Loads the canonical GLB (an authored sibling, or a cached conversion),
// then preserves animation or batches static geometry for mixed reality.
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { type BatchedModel, batchModel, disposeScene } from "./batching";
import { animatedModel, type ModelAnimation } from "./animation";

export type XRModel = Pick<BatchedModel, "root" | "bounds" | "stats"> & { animation?: ModelAnimation };

export type Progress = (message: string) => void;

export interface LoadTimes {
  /** Conversion (if not cached) and download, seconds. */
  fetch: number;
  parse: number;
  batch: number;
}

/** The model's canonical GLB, converting with mpd2glb only when no sibling exists. */
export async function fetchGlb(modelUrl: string, progress: Progress): Promise<ArrayBuffer> {
  progress("Preparing the model… The first time can take a minute.");
  const response = await fetch(`/api/glb?url=${encodeURIComponent(modelUrl)}`);
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body.detail)
      .catch(() => response.statusText);
    throw new Error(`Couldn't load the model: ${detail}`);
  }
  const total = Number(response.headers.get("content-length")) || 0;
  if (!response.body || !total) return response.arrayBuffer();
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    received += value.length;
    progress(`Downloading… ${Math.min(100, Math.round((received / total) * 100))}%`);
  }
  const bytes = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  return bytes.buffer;
}

const nextFrame = () => new Promise((resolve) => requestAnimationFrame(resolve));

export async function loadModel(modelUrl: string, progress: Progress): Promise<{ model: XRModel; times: LoadTimes }> {
  const t0 = performance.now();
  const buffer = await fetchGlb(modelUrl, progress);
  const t1 = performance.now();
  progress("Almost ready…");
  await nextFrame();
  const draco = new DRACOLoader().setDecoderPath("/viewer/vendor/gltf/draco/");
  const loader = new GLTFLoader().setDRACOLoader(draco).setMeshoptDecoder(MeshoptDecoder);
  const resourcePath = new URL(".", new URL(modelUrl, location.href)).href;
  const gltf = await loader.parseAsync(buffer, resourcePath).finally(() => draco.dispose());
  const t2 = performance.now();
  await nextFrame();
  const model = gltf.animations.length ? animatedModel(gltf.scene, gltf.animations) : batchModel(gltf.scene);
  if (!gltf.animations.length) disposeScene(gltf.scene);
  const t3 = performance.now();
  return { model, times: { fetch: (t1 - t0) / 1000, parse: (t2 - t1) / 1000, batch: (t3 - t2) / 1000 } };
}
