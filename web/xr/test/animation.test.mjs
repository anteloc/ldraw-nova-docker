import { describe, expect, it } from 'vitest';
import { AnimationClip, Box3, BoxGeometry, Group, Mesh, MeshStandardMaterial, Vector3, VectorKeyframeTrack } from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { animatedModel } from '../src/animation';
import { animatedGlb, quantizedGlb } from './fixtures/animated-glb.mjs';

async function load(quantized = false) {
  const bytes = await (quantized ? quantizedGlb() : animatedGlb());
  const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
  const model = animatedModel(gltf.scene, gltf.animations);
  const pose = () => ({
    rigid: gltf.scene.getObjectByName('moving').position.x,
    morph: gltf.scene.getObjectByName('morph').morphTargetInfluences[0],
    bone: gltf.scene.getObjectByName('tip').quaternion.z,
    time: model.animation.mixer.time,
  });
  return { model, gltf, pose };
}

describe('VR model animation', () => {
  it.each([false, true])('starts paused, then plays rigid, morph and bone clips (quantized: %s)', async quantized => {
    const { model, gltf, pose } = await load(quantized);
    expect(model.root.children[0]).toBe(gltf.scene);
    const start = pose();
    expect(model.animation.update(1)).toBe(false);
    expect(pose()).toEqual(start);
    const initial = model.bounds.clone();
    model.animation.setPlaying(true);
    for (let i = 0; i < 50; i++) model.animation.update(0.1);
    expect(pose().rigid).toBeGreaterThan(start.rigid);
    expect(pose().morph).toBeGreaterThan(start.morph);
    expect(pose().bone).toBeGreaterThan(start.bone);
    expect(model.bounds.equals(initial)).toBe(false);
    model.animation.setPlaying(false);
    const paused = pose();
    model.animation.update(10);
    expect(pose()).toEqual(paused);
    model.animation.setPlaying(true);
    model.animation.update(0.05);
    expect(pose().time).toBeCloseTo(paused.time + 0.05);
    model.animation.dispose();
    expect(model.animation.playing).toBe(false);
  });

  it('keeps model-space bounds and the placement transform stable when moved, rotated and scaled', async () => {
    const { model } = await load(true);
    const original = model.bounds.clone();
    const holder = new Group();
    holder.add(model.root);
    holder.position.set(10, 2, -5);
    holder.rotation.set(0.2, 0.7, -0.3);
    holder.scale.setScalar(12);
    model.root.position.set(-0.2, 0.12, 0.3);
    model.animation.setPlaying(true);
    model.animation.update(0);
    expect(model.bounds.min.distanceTo(original.min)).toBeLessThan(1e-6);
    expect(model.bounds.max.distanceTo(original.max)).toBeLessThan(1e-6);
    model.animation.update(0.1);
    expect(holder.position.toArray()).toEqual([10, 2, -5]);
    expect(holder.scale.toArray()).toEqual([12, 12, 12]);
    expect(model.root.position.toArray()).toEqual([-0.2, 0.12, 0.3]);
    expect(model.bounds.getSize(new Vector3()).length()).toBeLessThan(1);
  });

  it('loops all clips and clamps long frame gaps', async () => {
    const { model, pose } = await load();
    model.animation.setPlaying(true);
    model.animation.update(60);
    expect(pose().time).toBeCloseTo(0.1);
    for (let i = 0; i < 200; i++) model.animation.update(0.1);
    expect(pose().rigid).toBeCloseTo(0.0025);
    expect(pose().morph).toBeCloseTo(0.01);
  });

  it('batches rigid subassemblies under their animated pivots, including constant exported tracks', () => {
    const scene = new Group(), pivot = new Group();
    pivot.name = 'pivot';
    scene.add(pivot);
    const geometry = new BoxGeometry(0.1, 0.1, 0.1), material = new MeshStandardMaterial();
    const sources = [];
    for (let i = 0; i < 20; i++) {
      const part = new Mesh(geometry, material);
      part.name = `part${i}`;
      part.position.x = i * 0.12;
      pivot.add(part);
      sources.push(part);
    }
    const stationary = new Mesh(geometry, material);
    scene.add(stationary);
    sources.push(stationary);
    const clips = [new AnimationClip('move', 2, [
      new VectorKeyframeTrack('pivot.position', [0, 1, 2], [0, 0, 0, 0, 1, 0, 0, 0, 0]),
      new VectorKeyframeTrack('part0.position', [0, 1, 2], [0, 0, 0, 0, 0, 0, 0, 0, 0]),
    ])];
    const model = animatedModel(scene, clips);
    expect(model.stats.batches).toBe(2); // 21 parts, two draw calls, even while moving
    expect(sources.slice(0, 20).every(mesh => mesh.layers.mask === 0)).toBe(true);
    expect(stationary.layers.mask).toBe(1); // a singleton keeps its native draw
    model.animation.setPlaying(true);
    for (let i = 0; i < 5; i++) model.animation.update(0.1);
    expect(pivot.position.y).toBeCloseTo(0.5);
    const expected = new Box3();
    geometry.computeBoundingBox();
    for (const mesh of sources) expected.union(geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld));
    expect(model.bounds.min.distanceTo(expected.min)).toBeLessThan(1e-6);
    expect(model.bounds.max.distanceTo(expected.max)).toBeLessThan(1e-6);
    const batch = pivot.children.find(child => child.name === 'ldraw-model').children[0];
    expect(batch.isBatchedMesh).toBe(true);
    expect(batch.layers.mask).toBe(1);
    expect(batch.getWorldPosition(new Vector3()).y).toBeCloseTo(0.5);
  });
});
