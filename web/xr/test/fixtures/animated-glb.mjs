// Small authored GLB exercising rigid, skeletal and morph animation together.
// Generated in memory so the regression test doesn't need another binary asset.
import {
  AnimationClip, Bone, BoxGeometry, EdgesGeometry, Float32BufferAttribute, Group,
  LineBasicMaterial, LineSegments, Mesh, MeshStandardMaterial, NumberKeyframeTrack,
  QuaternionKeyframeTrack, Skeleton, SkinnedMesh, Uint16BufferAttribute, VectorKeyframeTrack,
} from 'three';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';

// GLTFExporter uses the browser FileReader API to pack its binary buffers.
globalThis.FileReader ??= class {
  async readAsArrayBuffer(blob) { this.result = await blob.arrayBuffer(); this.onloadend?.(); }
  async readAsDataURL(blob) {
    this.result = `data:${blob.type};base64,${Buffer.from(await blob.arrayBuffer()).toString('base64')}`;
    this.onloadend?.();
  }
};

export async function animatedGlb(animated = true) {
  const root = new Group();
  const material = new MeshStandardMaterial({ color: 0x1c7ccc, roughness: 0.72, metalness: 0.23 });
  const moving = new Mesh(new BoxGeometry(0.12, 0.12, 0.12), material);
  moving.name = 'moving';
  moving.userData.type = 'Part';
  moving.add(new LineSegments(new EdgesGeometry(moving.geometry), new LineBasicMaterial({ color: 0x222222 })));

  const morphGeometry = new BoxGeometry(0.12, 0.12, 0.12);
  const morphPositions = morphGeometry.attributes.position.clone();
  for (let i = 0; i < morphPositions.count; i++) morphPositions.setY(i, morphPositions.getY(i) * 2);
  morphGeometry.morphAttributes.position = [morphPositions];
  const morph = new Mesh(morphGeometry, material);
  morph.name = 'morph';
  morph.position.x = -0.2;
  morph.userData.type = 'Part';

  const skinGeometry = new BoxGeometry(0.12, 0.24, 0.12);
  const joints = [], weights = [];
  for (let i = 0; i < skinGeometry.attributes.position.count; i++) {
    joints.push(skinGeometry.attributes.position.getY(i) > 0 ? 1 : 0, 0, 0, 0);
    weights.push(1, 0, 0, 0);
  }
  skinGeometry.setAttribute('skinIndex', new Uint16BufferAttribute(joints, 4));
  skinGeometry.setAttribute('skinWeight', new Float32BufferAttribute(weights, 4));
  const skin = new SkinnedMesh(skinGeometry, material);
  skin.name = 'skin';
  skin.userData.type = 'Part';
  skin.position.x = 0.2;
  const base = new Bone(), tip = new Bone();
  tip.name = 'tip';
  base.add(tip);
  skin.add(base);
  skin.bind(new Skeleton([base, tip]));
  root.add(moving, morph, skin);
  const times = [0, 10, 20];
  const clips = animated ? [
    new AnimationClip('Slide', 20, [new VectorKeyframeTrack('moving.position', times, [0, 0, 0, 0.25, 0, 0, 0, 0, 0])]),
    new AnimationClip('Stretch', 20, [new NumberKeyframeTrack('morph.morphTargetInfluences', times, [0, 1, 0])]),
    new AnimationClip('Bend', 20, [new QuaternionKeyframeTrack('tip.quaternion', times, [0, 0, 0, 1, 0, 0, Math.sin(0.5), Math.cos(0.5), 0, 0, 0, 1])]),
  ] : [];
  return Buffer.from(await new GLTFExporter().parseAsync(root, { binary: true, animations: clips }));
}

// Quantize the positions, morphs and skin weights without requiring a separate
// compression package. Exercises KHR_mesh_quantization's normalized accessors.
export async function quantizedGlb() {
  const buffer = await animatedGlb();
  const jsonLength = buffer.readUInt32LE(12);
  const json = JSON.parse(buffer.subarray(20, 20 + jsonLength));
  const binary = Buffer.from(buffer.subarray(28 + jsonLength));
  const attributes = new Map();
  for (const mesh of json.meshes) for (const primitive of mesh.primitives) {
    for (const name of ['POSITION', 'NORMAL', 'WEIGHTS_0']) {
      if (primitive.attributes[name] !== undefined) attributes.set(primitive.attributes[name], name === 'WEIGHTS_0');
    }
    for (const target of primitive.targets ?? []) for (const accessor of Object.values(target)) attributes.set(accessor, false);
  }
  for (const [index, unsigned] of attributes) {
    const accessor = json.accessors[index], view = json.bufferViews[accessor.bufferView];
    const size = { VEC3: 3, VEC4: 4 }[accessor.type];
    const offset = (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
    const values = Array.from({ length: accessor.count * size }, (_, i) => binary.readFloatLE(offset + i * 4));
    const scale = unsigned ? 65535 : 32767;
    // Vertex attributes start on four-byte boundaries, including VEC3 padding.
    const stride = Math.ceil(size * 2 / 4) * 4;
    values.forEach((value, i) => {
      const address = offset + Math.floor(i / size) * stride + (i % size) * 2;
      if (unsigned) binary.writeUInt16LE(Math.round(value * scale), address);
      else binary.writeInt16LE(Math.round(value * scale), address);
    });
    accessor.componentType = unsigned ? 5123 : 5122;
    accessor.normalized = true;
    for (const key of ['min', 'max']) if (accessor[key]) accessor[key] = accessor[key].map(v => Math.round(v * scale));
    view.byteStride = stride;
    view.byteLength = accessor.count * stride;
  }
  json.extensionsUsed = [...new Set([...(json.extensionsUsed ?? []), 'KHR_mesh_quantization'])];
  json.extensionsRequired = [...new Set([...(json.extensionsRequired ?? []), 'KHR_mesh_quantization'])];
  const text = Buffer.from(JSON.stringify(json));
  const padded = Buffer.alloc(Math.ceil(text.length / 4) * 4, 32);
  text.copy(padded);
  const header = Buffer.alloc(20), binaryHeader = Buffer.alloc(8);
  header.write('glTF'); header.writeUInt32LE(2, 4);
  header.writeUInt32LE(28 + padded.length + binary.length, 8);
  header.writeUInt32LE(padded.length, 12); header.write('JSON', 16);
  binaryHeader.writeUInt32LE(binary.length); binaryHeader.write('BIN\0', 4);
  return Buffer.concat([header, padded, binaryHeader, binary]);
}
