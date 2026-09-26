// Performance numbers for tuning on the headset: frame rate and time, CPU time
// in IWSDK's systems and in render submission, draw calls and triangles.
// Shown in the menu (Stats) or the page, and logged every few seconds, so they
// can be read with chrome://inspect over adb.
import type { World } from "@iwsdk/core";

export interface Sample {
  fps: number;
  /** Mean time between frames, ms. */
  frameMs: number;
  /** Mean CPU time in world.update (all ECS systems), ms. */
  updateMs: number;
  /** Mean CPU time in renderer.render (culling, sorting, issuing draws), ms. */
  renderMs: number;
  /** Per frame (both eyes: one draw each with multiview). */
  drawCalls: number;
  triangles: number;
}

export class PerfMeter {
  private frames = 0;
  private start = 0;
  private update = 0;
  private render = 0;
  private drawCalls = 0;
  private triangles = 0;
  latest: Sample | null = null;

  constructor(world: World) {
    const renderer = world.renderer;
    const render = renderer.render.bind(renderer);
    renderer.render = (scene, camera) => {
      const t = performance.now();
      render(scene, camera);
      this.render += performance.now() - t;
      this.drawCalls = renderer.info.render.calls;
      this.triangles = renderer.info.render.triangles;
      this.frame(t);
    };
    const update = world.update.bind(world);
    world.update = (delta, time) => {
      const t = performance.now();
      update(delta, time);
      this.update += performance.now() - t;
    };
  }

  private frame(now: number) {
    if (this.start === 0) this.start = now;
    this.frames++;
    if (now - this.start >= 1000) {
      const n = this.frames;
      this.latest = {
        fps: (n * 1000) / (now - this.start),
        frameMs: (now - this.start) / n,
        updateMs: this.update / n,
        renderMs: this.render / n,
        drawCalls: this.drawCalls,
        triangles: this.triangles,
      };
      this.start = now;
      this.frames = 0;
      this.update = 0;
      this.render = 0;
    }
  }
}

export function formatSample(s: Sample): string {
  const tris = s.triangles >= 1e6 ? `${(s.triangles / 1e6).toFixed(2)}M` : `${Math.round(s.triangles / 1e3)}K`;
  return (
    `${s.fps.toFixed(0)} fps · ${s.frameMs.toFixed(1)} ms/frame · ` +
    `systems ${s.updateMs.toFixed(1)} ms · render ${s.renderMs.toFixed(1)} ms · ` +
    `${s.drawCalls} draws · ${tris} triangles`
  );
}
