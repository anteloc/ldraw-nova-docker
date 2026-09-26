// Load-time batching: turns mpd2glb's GLB (one node per placed part, meshes
// shared per part geometry × colour) into at most four BatchedMeshes, i.e. at
// most four draw calls however big the model is:
//
//   opaque | transparent  ×  normal | mirrored
//
// Each unique geometry is uploaded once per batch and welded (made indexed:
// mpd2glb writes non-indexed triangles, so every vertex would be shaded about
// twice as often). Each placed part becomes an instance with its own matrix and
// colour. Mirrored placements (negative determinant) get a copy of the
// geometry with reversed winding, so all batches can cull back faces; a
// BackSide material would light them from the wrong side.
//
// Edge lines are left out: 1 px lines alias badly in a headset and cost as
// much as a third of the vertices. Materials are Blinn-Phong, for the glossy
// highlights of ABS plastic: no PBR, no environment map, no shadows.
//
// Imports `three` directly (not via @iwsdk/core) so the tests run in Node;
// both resolve to the same super-three package (see vite.config.ts).
import {
  BatchedMesh,
  Box3,
  BufferGeometry,
  type Camera,
  Color,
  Frustum,
  Group,
  Matrix4,
  type Material,
  type Mesh,
  MeshPhongMaterial,
  type Object3D,
  Sphere,
} from "three";
import { deinterleaveGeometry, mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/** What mpd2glb records for every placed part (glTF node extras). */
export interface PartInfo {
  fileName: string;
  description: string;
  colorCode: string;
  step: number;
}

export interface BatchStats {
  /** Placed parts. */
  parts: number;
  /** Instances: one per part and colour (multi-colour parts have several). */
  instances: number;
  /** BatchedMeshes, i.e. draw calls per view. */
  batches: number;
  /** Unique geometries (mirrored copies counted separately). */
  geometries: number;
  /** Triangles drawn per view with every instance in sight. */
  triangles: number;
  /** Vertices of the unique geometries as loaded, and after welding. */
  verticesBefore: number;
  verticesAfter: number;
  mirrored: number;
  transparent: number;
  /** Edge-line meshes left out. */
  edges: number;
}

export interface BatchedModel {
  /** The model, in metres at real LEGO size (mpd2glb's scale). */
  root: Group;
  batches: BatchedMesh[];
  parts: PartInfo[];
  /** Per batch (same order): instance id → index into `parts`. */
  instanceParts: Int32Array[];
  /** Bounds of the model in `root` space. */
  bounds: Box3;
  stats: BatchStats;
}

export interface BatchOptions {
  /** One opacity for all transparent parts. @default 0.6 */
  transparentOpacity?: number;
}

type Kind = "opaque" | "opaque-mirrored" | "transparent" | "transparent-mirrored";
const KINDS: Kind[] = ["opaque", "opaque-mirrored", "transparent", "transparent-mirrored"];

interface Placement {
  geometry: BufferGeometry;
  matrix: Matrix4;
  color: Color;
  part: number;
}

type ColoredMaterial = Material & { color?: Color };

export function batchModel(scene: Object3D, options: BatchOptions = {}): BatchedModel {
  const opacity = options.transparentOpacity ?? 0.6;
  scene.updateMatrixWorld(true);
  const toRoot = scene.matrixWorld.clone().invert();

  const placements = new Map<Kind, Placement[]>(KINDS.map((k) => [k, []]));
  const parts: PartInfo[] = [];
  const partIds = new Map<Object3D, number>();
  let edges = 0;

  const partOf = (object: Object3D): number => {
    let node: Object3D | null = object;
    while (node && node.userData?.fileName === undefined) node = node.parent;
    const key = node ?? object;
    let id = partIds.get(key);
    if (id === undefined) {
      const extras = node?.userData ?? {};
      id = parts.length;
      parts.push({
        fileName: String(extras.fileName ?? object.name ?? ""),
        description: String(extras.description ?? ""),
        colorCode: String(extras.colorCode ?? ""),
        step: Number(extras.buildingStep ?? 0),
      });
      partIds.set(key, id);
    }
    return id;
  };

  scene.traverse((object) => {
    if ((object as { isLine?: boolean }).isLine) {
      edges++;
      return;
    }
    const mesh = object as Mesh;
    if (!mesh.isMesh) return;
    const material = (Array.isArray(mesh.material) ? mesh.material[0] : mesh.material) as ColoredMaterial;
    const matrix = new Matrix4().multiplyMatrices(toRoot, mesh.matrixWorld);
    const transparent = material.transparent || material.opacity < 1;
    const mirrored = matrix.determinant() < 0;
    const kind = `${transparent ? "transparent" : "opaque"}${mirrored ? "-mirrored" : ""}` as Kind;
    placements.get(kind)!.push({
      geometry: mesh.geometry,
      matrix,
      color: material.color ? material.color.clone() : new Color(1, 1, 1),
      part: partOf(mesh),
    });
  });

  const welded = new Map<BufferGeometry, BufferGeometry>();
  const flipped = new Map<BufferGeometry, BufferGeometry>();
  const weld = (geometry: BufferGeometry) => {
    let result = welded.get(geometry);
    if (!result) {
      result = weldGeometry(geometry);
      welded.set(geometry, result);
    }
    return result;
  };
  const flip = (geometry: BufferGeometry) => {
    let result = flipped.get(geometry);
    if (!result) {
      result = flipWinding(geometry);
      flipped.set(geometry, result);
    }
    return result;
  };

  const root = new Group();
  root.name = "ldraw-model";
  const batches: BatchedMesh[] = [];
  const instanceParts: Int32Array[] = [];
  const bounds = new Box3();
  let triangles = 0;
  let geometries = 0;

  for (const kind of KINDS) {
    const list = placements.get(kind)!;
    if (list.length === 0) continue;
    const mirrored = kind.endsWith("mirrored");
    const transparent = kind.startsWith("transparent");
    const prepared = list.map((p) => (mirrored ? flip(weld(p.geometry)) : weld(p.geometry)));

    const unique = [...new Set(prepared)];
    const vertexCount = unique.reduce((n, g) => n + g.getAttribute("position").count, 0);
    const indexCount = unique.reduce((n, g) => n + g.index!.count, 0);
    const material = new MeshPhongMaterial({
      color: 0xffffff, // times each part's colour
      specular: 0x333333,
      shininess: 60,
      transparent,
      opacity: transparent ? opacity : 1,
      depthWrite: !transparent,
    });
    const batch = new BatchedMesh(list.length, vertexCount, indexCount, material);
    batch.name = kind;
    const geometryIds = new Map(unique.map((g) => [g, batch.addGeometry(g)]));
    const partsOfBatch = new Int32Array(list.length);
    list.forEach((placement, i) => {
      const geometry = prepared[i];
      const id = batch.addInstance(geometryIds.get(geometry)!);
      batch.setMatrixAt(id, placement.matrix);
      batch.setColorAt(id, placement.color);
      partsOfBatch[id] = placement.part;
      triangles += geometry.index!.count / 3;
    });
    cullInstances(batch); // pays off once you walk into a model
    batch.matrixAutoUpdate = false;
    // Pointers ray-test the model every frame; thousands of instances must not
    // be part of that. A plain bounds box stands in for them (see interaction.ts).
    batch.raycast = () => {};
    batch.computeBoundingBox();
    batch.computeBoundingSphere();
    bounds.union(batch.boundingBox!);
    root.add(batch);
    batches.push(batch);
    instanceParts.push(partsOfBatch);
    geometries += unique.length;
  }

  let verticesBefore = 0;
  let verticesAfter = 0;
  for (const [original, result] of welded) {
    verticesBefore += original.getAttribute("position").count;
    verticesAfter += result.getAttribute("position").count;
  }

  return {
    root,
    batches,
    parts,
    instanceParts,
    bounds,
    stats: {
      parts: parts.length,
      instances: batches.reduce((n, b) => n + b.instanceCount, 0),
      batches: batches.length,
      geometries,
      triangles,
      verticesBefore,
      verticesAfter,
      mirrored: (placements.get("opaque-mirrored")!.length + placements.get("transparent-mirrored")!.length),
      transparent: (placements.get("transparent")!.length + placements.get("transparent-mirrored")!.length),
      edges,
    },
  };
}

/** BatchedMesh internals that cullInstances drives (three.js r181). */
interface BatchedInternals {
  _instanceInfo: { geometryIndex: number }[];
  _geometryInfo: { start: number; count: number }[];
  _multiDrawStarts: Int32Array;
  _multiDrawCounts: Int32Array;
  _multiDrawCount: number;
  _indirectTexture: { image: { data: Uint32Array }; needsUpdate: boolean };
  _visibilityChanged: boolean;
}

const _frustum = new Frustum();
const _sphere = new Sphere();
const _matrix = new Matrix4();

// Per-part frustum culling with a draw list that never changes.
//
// BatchedMesh's own culling (and sorting) rebuilds its draw list whenever the
// view changes. Which part each draw slot is lives in a texture, and with
// multiview (the Quest) super-three uploads textures only after the frame,
// while the slots' geometry ranges take effect at once: for a frame after every
// head turn, slots drew other parts' shapes at their places, in their colours
// (pieces swapping). Here slot i is always part i, so that texture is written
// once; a part out of view keeps its slot with nothing to draw (count 0), and
// counts take effect in the same frame. Transparent parts aren't re-sorted by
// distance either (a sort is a changing list): overlapping glass may blend in
// the wrong order, which is hardly visible.
//
// The frustum is the camera's: for the XR two-eye camera (multiview), that's
// the union of both eyes, as WebXRManager sets it up for culling; per-eye
// rendering calls this once per eye.
export function cullInstances(batch: BatchedMesh) {
  const internals = batch as unknown as BatchedInternals;
  const count = batch.instanceCount;
  const index = batch.geometry.getIndex();
  const bytesPerIndex = index ? index.array.BYTES_PER_ELEMENT : 1;
  const starts = new Int32Array(count); // in bytes, as multiDrawElements takes them
  const counts = new Int32Array(count);
  const spheres = new Float32Array(count * 4); // parts never move within the batch
  const slots = internals._indirectTexture.image.data;
  for (let i = 0; i < count; i++) {
    const geometryId = internals._instanceInfo[i].geometryIndex;
    const range = internals._geometryInfo[geometryId];
    starts[i] = range.start * bytesPerIndex;
    counts[i] = range.count;
    batch.getBoundingSphereAt(geometryId, _sphere)!.applyMatrix4(batch.getMatrixAt(i, _matrix));
    _sphere.center.toArray(spheres, i * 4);
    spheres[i * 4 + 3] = _sphere.radius;
    slots[i] = i;
  }
  internals._indirectTexture.needsUpdate = true;
  batch.perObjectFrustumCulled = false; // three's culling and sorting are replaced
  batch.sortObjects = false;

  batch.onBeforeRender = function (_renderer, _scene, camera: Camera) {
    // the frustum in the batch's own space, where the spheres are
    _matrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).multiply(this.matrixWorld);
    _frustum.setFromProjectionMatrix(_matrix, camera.coordinateSystem, camera.reversedDepth);
    const drawStarts = internals._multiDrawStarts;
    const drawCounts = internals._multiDrawCounts;
    for (let i = 0; i < count; i++) {
      _sphere.center.fromArray(spheres, i * 4);
      _sphere.radius = spheres[i * 4 + 3];
      drawStarts[i] = starts[i];
      drawCounts[i] = _frustum.intersectsSphere(_sphere) ? counts[i] : 0;
    }
    internals._multiDrawCount = count;
    internals._visibilityChanged = false;
  };
}

// With multiview, super-three 0.181 starts the vertex shader with
// `layout(num_views = 2) in;` and only then adds the `#extension
// GL_ANGLE_multi_draw` line that BatchedMesh needs. ESSL 3 rejects that
// ("extension directive must occur before any non-preprocessor tokens"), so the
// model's shader doesn't compile and nothing of it shows, while everything else
// does. Call with the renderer's context before anything renders.
export function fixShaderExtensions(gl: WebGL2RenderingContext) {
  const shaderSource = gl.shaderSource.bind(gl);
  gl.shaderSource = (shader, source) => shaderSource(shader, hoistExtensions(source));
}

/** Moves every #extension line up to right after #version (three.js never puts one inside an #if). */
export function hoistExtensions(source: string): string {
  const lines = source.split("\n");
  const isExtension = (line: string) => line.trimStart().startsWith("#extension");
  const extensions = lines.filter(isExtension);
  if (!extensions.length) return source;
  const rest = lines.filter((line) => !isExtension(line));
  rest.splice(rest[0]?.startsWith("#version") ? 1 : 0, 0, ...extensions);
  return rest.join("\n");
}

/** Indexed copy with only positions and normals (what BatchedMesh needs), shared vertices merged. */
export function weldGeometry(geometry: BufferGeometry): BufferGeometry {
  let source = new BufferGeometry();
  source.setAttribute("position", geometry.getAttribute("position"));
  const normal = geometry.getAttribute("normal");
  if (normal) source.setAttribute("normal", normal);
  if (geometry.index) source.setIndex(geometry.index);
  // GLTFLoader gives interleaved attributes (positions and normals share a
  // buffer); mergeVertices needs plain ones. Copies, so the original is untouched.
  deinterleaveGeometry(source);
  if (!normal) {
    // Flat normals first: welding before would smooth across hard edges.
    source = source.index ? source.toNonIndexed() : source;
    source.computeVertexNormals();
  }
  const result = mergeVertices(source); // always indexed, as BatchedMesh needs
  result.computeBoundingBox();
  result.computeBoundingSphere();
  return result;
}

/** Copy with every triangle's winding reversed. */
export function flipWinding(geometry: BufferGeometry): BufferGeometry {
  const result = geometry.clone();
  const index = result.index!;
  const array = index.array;
  for (let i = 0; i < array.length; i += 3) {
    const b = array[i + 1];
    array[i + 1] = array[i + 2];
    array[i + 2] = b;
  }
  index.needsUpdate = true;
  return result;
}

/** Frees the loaded glTF scene once it has been batched. */
export function disposeScene(scene: Object3D) {
  scene.traverse((object) => {
    const mesh = object as Mesh;
    mesh.geometry?.dispose();
    const materials = Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [];
    materials.forEach((m) => m.dispose());
  });
}
