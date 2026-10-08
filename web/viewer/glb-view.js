// GLB scene adapter for viewer.html's shared camera and lighting controls.
// Keep the authored graph intact: animation bindings, skins, morph targets,
// textures and edge lines must survive every rendering-mode change.
/* global THREE */
var GLBView = (function () {
  const VENDOR = new URL('vendor/gltf/', document.baseURI).href;
  let dependencies;

  function script(url) {
    return new Promise((resolve, reject) => {
      const element = document.createElement('script');
      element.src = url;
      element.onload = resolve;
      element.onerror = () => reject(new Error('Could not load the GLB decoder.'));
      document.head.append(element);
    });
  }

  // r139's CPU attribute accessors don't decode normalized integers. Convert
  // them once so bounds, morphs and boneTransform use the same values as GLSL.
  function decodeNormalized(attribute, cache) {
    if (!attribute.normalized) return attribute;
    if (cache.has(attribute)) return cache.get(attribute);
    const interleaved = attribute.isInterleavedBufferAttribute;
    const array = interleaved ? attribute.data.array : attribute.array;
    const stride = interleaved ? attribute.data.stride : attribute.itemSize;
    const offset = interleaved ? attribute.offset : 0;
    const values = new Float32Array(attribute.count * attribute.itemSize);
    for (let i = 0; i < attribute.count; i++) {
      for (let j = 0; j < attribute.itemSize; j++) {
        values[i * attribute.itemSize + j] = THREE.MathUtils.denormalize(array[i * stride + offset + j], array);
      }
    }
    const decoded = new THREE.Float32BufferAttribute(values, attribute.itemSize);
    cache.set(attribute, decoded);
    return decoded;
  }

  class GLBView {
    static async load(canvas, buffer, resourcePath) {
      dependencies ??= Promise.all([
        script(VENDOR + 'GLTFLoader.js'),
        script(VENDOR + 'DRACOLoader.js'),
        import(VENDOR + 'meshopt_decoder.module.js'),
      ]);
      const [, , { MeshoptDecoder }] = await dependencies;
      const draco = new THREE.DRACOLoader().setDecoderPath(VENDOR + 'draco/');
      const loader = new THREE.GLTFLoader().setDRACOLoader(draco).setMeshoptDecoder(MeshoptDecoder);
      const gltf = await loader.parseAsync(buffer, resourcePath).finally(() => draco.dispose());
      return new GLBView(canvas, gltf);
    }

    constructor(canvas, gltf) {
      this.isGLB = true;
      this.container = canvas.parentNode;
      this.scene = new THREE.Scene();
      this.scene.background = new THREE.Color(0xf2f2f2);
      this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
      this.root = gltf.scene;
      this.meshes = [];
      this.lines = [];
      this.materials = new Map();
      this.partCount = 0;
      const attributes = new Map(), geometries = new Set();
      this.root.traverse(object => {
        const geometry = object.geometry;
        if (geometry && !geometries.has(geometry)) {
          geometries.add(geometry);
          for (const [name, attribute] of Object.entries(geometry.attributes)) {
            geometry.setAttribute(name, decodeNormalized(attribute, attributes));
          }
          for (const [name, targets] of Object.entries(geometry.morphAttributes)) {
            geometry.morphAttributes[name] = targets.map(attribute => decodeNormalized(attribute, attributes));
          }
        }
        if (object.userData.type === 'Part') this.partCount++;
        if (object.isMesh) {
          this.meshes.push({ object, material: object.material });
          object.castShadow = object.receiveShadow = true;
          // Rest-pose bounds don't describe a deforming mesh throughout a clip.
          if (object.isSkinnedMesh || object.morphTargetInfluences) object.frustumCulled = false;
        } else if (object.isLine) {
          this.lines.push({ object, visible: object.visible });
        }
      });

      this.clips = gltf.animations;
      this.playing = false;
      this.animationFrame = null;
      this.lastTime = null;
      this.mixer = new THREE.AnimationMixer(this.root);
      for (const clip of this.clips) this.mixer.clipAction(clip).play();
      // Start paused at the clips' first frame; Play resumes this same mixer.
      this.mixer.update(0);

      // GLB uses metres. The shared camera's distances and speeds use LDraw
      // units (1 LDU = 0.4 mm). Wrap, rather than edit, animated root transforms.
      const units = new THREE.Group();
      units.scale.setScalar(2500);
      units.add(this.root);
      this.baseObject = new THREE.Group();
      this.baseObject.add(units);
      const box = this.getBounds();
      if (!box.isEmpty()) this.baseObject.position.copy(box.getCenter(new THREE.Vector3())).negate();
      this.scene.add(this.baseObject);

      this.amblight = new THREE.AmbientLight(0x656565);
      this.hemisphereLight = new THREE.HemisphereLight(0xf4f4fb, 0x30302b, 0.65);
      this.directionalLights = [new THREE.DirectionalLight(0xffffff, 0.4)];
      this.pointLights = [];
      this.scene.add(this.amblight, this.hemisphereLight, ...this.directionalLights);
    }

    // r139's Box3 uses undeformed geometry. Skinning can also undo GLB position
    // quantization, so those bounds may be much larger than the visible model.
    getBounds() {
      this.baseObject.updateMatrixWorld(true);
      const box = new THREE.Box3(), localBox = new THREE.Box3();
      const vertex = new THREE.Vector3(), base = new THREE.Vector3(), morph = new THREE.Vector3();
      for (const { object } of this.meshes) {
        const geometry = object.geometry;
        if (!object.isSkinnedMesh && !object.morphTargetInfluences) {
          if (!geometry.boundingBox) geometry.computeBoundingBox();
          box.union(localBox.copy(geometry.boundingBox).applyMatrix4(object.matrixWorld));
          continue;
        }
        const positions = geometry.attributes.position;
        for (let i = 0; i < positions.count; i++) {
          base.fromBufferAttribute(positions, i);
          vertex.copy(base);
          for (let j = 0; j < (geometry.morphAttributes.position?.length ?? 0); j++) {
            const weight = object.morphTargetInfluences[j];
            if (!weight) continue;
            morph.fromBufferAttribute(geometry.morphAttributes.position[j], i);
            if (!geometry.morphTargetsRelative) morph.sub(base);
            vertex.addScaledVector(morph, weight);
          }
          if (object.isSkinnedMesh) object.boneTransform(i, vertex);
          box.expandByPoint(vertex.applyMatrix4(object.matrixWorld));
        }
      }
      return box;
    }

    materialFor(original, mode) {
      if (mode === 'high') return original; // authored PBR, textures, transparency, etc.
      let variants = this.materials.get(original);
      if (!variants) this.materials.set(original, variants = {});
      if (!variants[mode]) {
        const color = original.color ? original.color.clone() : new THREE.Color(0xffffff);
        if (mode === 'poly') {
          const hsl = color.getHSL({});
          if (hsl.l > 0.82) color.setHSL(hsl.h, hsl.s, 0.62);
        }
        variants[mode] = new THREE.MeshBasicMaterial({
          color, side: original.side, vertexColors: original.vertexColors,
          wireframe: mode === 'poly',
          map: mode === 'normal' ? original.map : null,
          alphaMap: mode === 'normal' ? original.alphaMap : null,
          alphaTest: mode === 'normal' ? original.alphaTest : 0,
          opacity: mode === 'normal' ? original.opacity : 1,
          transparent: mode === 'normal' && original.transparent,
          depthWrite: mode === 'normal' ? original.depthWrite : true,
        });
      }
      return variants[mode];
    }

    setMaterials(mode) {
      for (const { object, material } of this.meshes) {
        object.material = Array.isArray(material)
          ? material.map(m => this.materialFor(m, mode)) : this.materialFor(material, mode);
      }
      // Edges stay in their animated parents, rather than being merged in world space.
      for (const { object, visible } of this.lines) object.visible = visible && mode !== 'poly';
    }

    setPlaying(playing) {
      this.playing = playing && this.clips.length > 0;
      if (this.animationFrame !== null) cancelAnimationFrame(this.animationFrame);
      this.animationFrame = null;
      this.lastTime = null;
      if (!this.playing) return;
      const step = now => {
        if (!this.playing) return;
        const delta = this.lastTime === null ? 0 : Math.min(0.1, (now - this.lastTime) / 1000);
        this.lastTime = now;
        this.mixer.update(delta);
        if (this.renderer.shadowMap.enabled) this.renderer.shadowMap.needsUpdate = true;
        this.render();
        this.animationFrame = requestAnimationFrame(step);
      };
      this.animationFrame = requestAnimationFrame(step);
    }

    dispose() {
      this.setPlaying(false);
      this.mixer.stopAllAction();
      this.mixer.uncacheRoot(this.root);
      for (const variants of this.materials.values()) for (const material of Object.values(variants)) material.dispose();
      this.renderer.dispose();
    }
  }
  return GLBView;
})();
