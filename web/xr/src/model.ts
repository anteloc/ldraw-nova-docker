// Loads a model for mixed reality: the backend converts it to .glb with
// mpd2glb (and caches it); here it's parsed and batched (batching.ts).
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { type BatchedModel, batchModel, disposeScene } from "./batching";

export type Progress = (message: string) => void;

export interface LoadTimes {
  /** Conversion (if not cached) and download, seconds. */
  fetch: number;
  parse: number;
  batch: number;
}

/** The model as GLB, from the backend (`/api/glb`, converted with mpd2glb and cached). */
export async function fetchGlb(modelUrl: string, progress: Progress): Promise<ArrayBuffer> {
  progress("Converting to .glb… big models take up to a minute the first time");
  const response = await fetch(`/api/glb?url=${encodeURIComponent(modelUrl)}`);
  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body.detail)
      .catch(() => response.statusText);
    throw new Error(`Could not convert the model: ${detail}`);
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

export async function loadModel(modelUrl: string, progress: Progress): Promise<{ model: BatchedModel; times: LoadTimes }> {
  const t0 = performance.now();
  const buffer = await fetchGlb(modelUrl, progress);
  const t1 = performance.now();
  progress("Reading the model…");
  await nextFrame();
  const gltf = await new GLTFLoader().parseAsync(buffer, "");
  const t2 = performance.now();
  progress("Batching…");
  await nextFrame();
  const model = batchModel(gltf.scene);
  disposeScene(gltf.scene);
  const t3 = performance.now();
  return { model, times: { fetch: (t1 - t0) / 1000, parse: (t2 - t1) / 1000, batch: (t3 - t2) / 1000 } };
}
