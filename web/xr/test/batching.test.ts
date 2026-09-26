import { readFileSync } from "node:fs";
import {
  BufferGeometry,
  Color,
  Float32BufferAttribute,
  Group,
  Mesh,
  MeshStandardMaterial,
  type Object3D,
  Vector3,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { describe, expect, it } from "vitest";
import { batchModel, flipWinding, weldGeometry } from "../src/batching";

// 8303-1 (from models-annotated), converted by the app's /api/glb (mpd2glb -c none).
async function loadFixture(): Promise<Object3D> {
  const file = readFileSync(new URL("./fixtures/8303-1.glb", import.meta.url));
  const buffer = file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength);
  const gltf = await new GLTFLoader().parseAsync(buffer, "");
  return gltf.scene;
}

// One triangle, non-indexed like mpd2glb's, facing +Z.
function triangle(): BufferGeometry {
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute([0, 0, 0, 1, 0, 0, 0, 1, 0], 3));
  geometry.setAttribute("normal", new Float32BufferAttribute([0, 0, 1, 0, 0, 1, 0, 0, 1], 3));
  return geometry;
}

describe("batchModel on a real mpd2glb model", () => {
  it("puts every placed part in at most four batches", async () => {
    const scene = await loadFixture();
    const colors = new Set<string>();
    let meshes = 0;
    scene.traverse((o) => {
      const mesh = o as Mesh;
      if (mesh.isMesh && !(o as { isLine?: boolean }).isLine) {
        meshes++;
        colors.add((mesh.material as MeshStandardMaterial).color.getHexString());
      }
    });

    const model = batchModel(scene);
    const { stats } = model;
    expect(stats.parts).toBe(50);
    expect(stats.instances).toBe(meshes);
    expect(stats.batches).toBeGreaterThan(0);
    expect(stats.batches).toBeLessThanOrEqual(4);
    expect(model.root.children).toHaveLength(stats.batches);
    expect(stats.edges).toBeGreaterThan(0); // left out
    expect(stats.verticesAfter).toBeLessThan(stats.verticesBefore); // welded

    // every instance keeps its part's colour
    const instanceColors = new Set<string>();
    const color = new Color();
    for (const batch of model.batches) {
      for (let id = 0; id < batch.instanceCount; id++) {
        batch.getColorAt(id, color);
        instanceColors.add(color.getHexString());
      }
    }
    expect(instanceColors).toEqual(colors);

    // part metadata from mpd2glb's node extras
    expect(model.parts.every((p) => /\.dat$/i.test(p.fileName))).toBe(true);
    expect(model.parts.filter((p) => p.description).length).toBeGreaterThan(40);
    expect(model.instanceParts.reduce((n, a) => n + a.length, 0)).toBe(stats.instances);

    // real LEGO size in metres: a small set, a few centimetres to decimetres
    const size = model.bounds.getSize(new Vector3());
    expect(Math.max(size.x, size.y, size.z)).toBeGreaterThan(0.03);
    expect(Math.max(size.x, size.y, size.z)).toBeLessThan(1);
    // upright: mpd2glb turns LDraw's -Y up into glTF's +Y up
    expect(size.y).toBeGreaterThan(0);
  });
});

describe("batchModel with mirrored and transparent parts", () => {
  it("separates them and reverses mirrored winding", () => {
    const scene = new Group();
    const geometry = triangle();
    const opaque = new MeshStandardMaterial({ color: 0xff0000 });
    const glass = new MeshStandardMaterial({ color: 0x00ff00, transparent: true, opacity: 0.5 });
    const a = new Mesh(geometry, opaque);
    const b = new Mesh(geometry, opaque);
    b.scale.set(-1, 1, 1); // mirrored
    b.position.x = 3;
    const c = new Mesh(geometry, glass);
    c.position.x = 6;
    scene.add(a, b, c);

    const model = batchModel(scene);
    expect(model.batches.map((m) => m.name)).toEqual(["opaque", "opaque-mirrored", "transparent"]);
    expect(model.stats).toMatchObject({ instances: 3, mirrored: 1, transparent: 1, batches: 3 });
    const glassMaterial = model.batches[2].material as MeshStandardMaterial;
    expect(glassMaterial.transparent).toBe(true);
    expect(glassMaterial.opacity).toBeCloseTo(0.6);
    expect(glassMaterial.depthWrite).toBe(false);
  });

  it("welds to an indexed geometry and flips each triangle", () => {
    const welded = weldGeometry(triangle());
    expect(Array.from(welded.index!.array)).toEqual([0, 1, 2]);
    expect(Object.keys(welded.attributes).sort()).toEqual(["normal", "position"]);
    const flipped = flipWinding(welded);
    expect(Array.from(flipped.index!.array)).toEqual([0, 2, 1]);
    expect(Array.from(welded.index!.array)).toEqual([0, 1, 2]); // original untouched
  });

  it("computes flat normals when the geometry has none, before welding", () => {
    const geometry = triangle();
    geometry.deleteAttribute("normal");
    const welded = weldGeometry(geometry);
    const normal = welded.getAttribute("normal");
    expect([normal.getX(0), normal.getY(0), normal.getZ(0)]).toEqual([0, 0, 1]);
  });
});
