// Animated GLBs keep their authored hierarchy, skins and morphs. Rigid parts
// sharing an animated ancestor are batched in that ancestor's local space.
import {
  AnimationMixer, type AnimationClip, type BatchedMesh, Box3, type BufferGeometry, Group, type InstancedMesh,
  type KeyframeTrack, Matrix4, type Mesh, type Object3D, PropertyBinding, type SkinnedMesh, Vector3,
} from "three";
import { batchModel, type BatchStats } from "./batching";

export class ModelAnimation {
  playing = false;
  private readonly inverse = new Matrix4();
  private readonly matrix = new Matrix4();
  private readonly box = new Box3();
  private readonly vertex = new Vector3();

  constructor(
    readonly mixer: AnimationMixer,
    private readonly root: Group,
    private readonly meshes: Mesh[],
    private readonly bounds: Box3,
  ) {
    this.updateBounds();
  }

  setPlaying(playing: boolean) {
    this.playing = playing;
  }

  /** Called by the XR frame loop; no separate desktop RAF or wall-clock jump. */
  update(delta: number) {
    if (!this.playing) return false;
    this.mixer.update(Math.min(Math.max(delta, 0), 0.1));
    this.updateBounds();
    return true;
  }

  private updateBounds() {
    this.root.updateWorldMatrix(true, false);
    // SkinnedMesh overrides updateMatrixWorld to refresh its bind inverse.
    this.root.updateMatrixWorld(true);
    this.inverse.copy(this.root.matrixWorld).invert();
    this.bounds.makeEmpty();
    for (const mesh of this.meshes) {
      this.matrix.multiplyMatrices(this.inverse, mesh.matrixWorld);
      if ((mesh as BatchedMesh).isBatchedMesh) {
        this.box.copy((mesh as BatchedMesh).boundingBox!);
      } else if ((mesh as InstancedMesh).isInstancedMesh) {
        const instances = mesh as InstancedMesh;
        if (!instances.boundingBox) instances.computeBoundingBox();
        this.box.copy(instances.boundingBox!);
      } else if ((mesh as SkinnedMesh).isSkinnedMesh || mesh.morphTargetInfluences?.length) {
        // Actual deformed vertices, including normalized/quantized accessors.
        // Keep the pointer box on the moving model, not its rest-pose bounds.
        this.box.makeEmpty();
        const count = mesh.geometry.getAttribute("position").count;
        for (let i = 0; i < count; i++) {
          mesh.getVertexPosition(i, this.vertex);
          this.box.expandByPoint(this.vertex);
        }
      } else {
        if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
        this.box.copy(mesh.geometry.boundingBox!);
      }
      this.bounds.union(this.box.applyMatrix4(this.matrix));
    }
  }

  dispose() {
    this.playing = false;
    this.mixer.stopAllAction();
    this.mixer.uncacheRoot(this.mixer.getRoot());
  }
}

export function animatedModel(scene: Group, clips: AnimationClip[]) {
  // Placement transforms belong to this outer group, never an animated node.
  const root = new Group();
  root.name = "ldraw-model";
  root.add(scene);
  const mixer = new AnimationMixer(scene);
  for (const clip of clips) mixer.clipAction(clip).play();
  mixer.update(0); // bake constant tracks at their first frame, initially paused
  const movingNodes = new Set<Object3D>();
  for (const clip of clips) for (const track of clip.tracks) {
    if (!changesOverTime(track)) continue;
    const binding = PropertyBinding.parseTrackName(track.name);
    const node = PropertyBinding.findNode(scene, binding.nodeName) as Object3D | null;
    if (node) movingNodes.add(node);
  }
  const bounds = new Box3();
  const meshes: Mesh[] = [];
  const parts = new Set<Object3D>(), geometries = new Set<BufferGeometry>();
  const stats: BatchStats = {
    parts: 0, instances: 0, batches: 0, geometries: 0, triangles: 0,
    verticesBefore: 0, verticesAfter: 0, mirrored: 0, transparent: 0, edges: 0,
  };
  scene.updateMatrixWorld(true);
  scene.traverse(object => {
    if ((object as { isLine?: boolean }).isLine) {
      object.visible = false; // same headset edge-line policy as static models
      stats.edges++;
    }
    const mesh = object as Mesh;
    if (!mesh.isMesh) return;
    meshes.push(mesh);
    // Deformed meshes cannot use cached rest-pose spheres for view culling.
    if ((mesh as SkinnedMesh).isSkinnedMesh || mesh.morphTargetInfluences?.length) mesh.frustumCulled = false;
    let part: Object3D | null = mesh;
    while (part && part.userData.fileName === undefined && part.userData.type !== "Part") part = part.parent;
    parts.add(part ?? mesh);
    geometries.add(mesh.geometry);
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    stats.batches += Array.isArray(mesh.material) ? mesh.geometry.groups.length : 1;
    stats.triangles += (mesh.geometry.index?.count ?? mesh.geometry.getAttribute("position").count) / 3;
    if (mesh.matrixWorld.determinant() < 0) stats.mirrored++;
    if (materials.some(material => material.transparent || material.opacity < 1)) stats.transparent++;
  });
  stats.parts = parts.size;
  stats.instances = meshes.length;
  stats.geometries = geometries.size;
  for (const geometry of geometries) stats.verticesBefore += geometry.getAttribute("position").count;
  stats.verticesAfter = stats.verticesBefore;
  const rendered: Mesh[] = [];
  const assemblies = new Map<Object3D, Set<Mesh>>();
  for (const mesh of meshes) {
    // Skin/morph deformation and textured or custom materials stay on the GPU
    // in their original meshes. Plain rigid parts use the existing VR shading.
    const material = mesh.material;
    const textured = !Array.isArray(material) && Object.entries(material).some(([key, value]) => /map$/i.test(key) && value);
    if ((mesh as SkinnedMesh).isSkinnedMesh || (mesh as InstancedMesh).isInstancedMesh ||
        mesh.morphTargetInfluences?.length || Array.isArray(material) || textured ||
        !["MeshBasicMaterial", "MeshStandardMaterial", "MeshPhysicalMaterial", "MeshPhongMaterial"].includes(material.type)) {
      rendered.push(mesh);
      continue;
    }
    let ancestor: Object3D = mesh;
    while (ancestor.parent && ancestor !== scene && !movingNodes.has(ancestor)) ancestor = ancestor.parent;
    let assembly = assemblies.get(ancestor);
    if (!assembly) assemblies.set(ancestor, assembly = new Set());
    assembly.add(mesh);
  }
  for (const [ancestor, assembly] of assemblies) {
    if (assembly.size === 1) {
      rendered.push(...assembly); // no draw-call saving; keep the original mesh
      continue;
    }
    const batched = batchModel(ancestor, { includeMesh: mesh => assembly.has(mesh) });
    ancestor.add(batched.root);
    rendered.push(...batched.batches);
    // Layers hide only the original draw, keeping children, bones and animation
    // targets alive. Hiding the parent object would also hide its new batches.
    for (const mesh of assembly) mesh.layers.disableAll();
  }
  stats.batches = rendered.reduce((n, mesh) => n + (Array.isArray(mesh.material) ? mesh.geometry.groups.length : 1), 0);
  const renderGeometries = new Set(rendered.map(mesh => mesh.geometry));
  stats.geometries = renderGeometries.size;
  stats.verticesAfter = [...renderGeometries].reduce((n, geometry) => n + geometry.getAttribute("position").count, 0);
  const animation = new ModelAnimation(mixer, root, rendered, bounds);
  return { root, bounds, stats, animation };
}

/** Exporters often key constant transforms on every frame; these need no separate batch. */
function changesOverTime(track: KeyframeTrack) {
  if (track.times.length < 2) return false;
  // Cubic tangents can create motion even with identical key values.
  if ((track as KeyframeTrack & { createInterpolant?: { isInterpolantFactoryMethodGLTFCubicSpline?: boolean } })
    .createInterpolant?.isInterpolantFactoryMethodGLTFCubicSpline) return true;
  const size = track.getValueSize();
  for (let i = size; i < track.values.length; i++) if (track.values[i] !== track.values[i % size]) return true;
  return false;
}
