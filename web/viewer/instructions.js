/* global THREE, LDR */
'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const missing = new Set(), unknownColours = new Set();
  let renderer, iconRenderer, controls, camera, scene, root, loader, handler, pli;
  let failed = false, loaded = false, authoredSteps = false;

  function status(text, kind = '') {
    $('status').textContent = text;
    $('status').className = kind;
  }
  function fail(error) {
    failed = true;
    for (const id of ['previous', 'next', 'step', 'home']) $(id).disabled = true;
    status(`Could not load build instructions: ${error.message || error}`, 'error');
  }
  function showStatus() {
    if (failed) return;
    const warnings = [];
    if (missing.size) warnings.push(`Missing parts shown as boxes: ${[...missing].slice(0, 5).join(', ')}${missing.size > 5 ? '…' : ''}.`);
    if (unknownColours.size) warnings.push(`Unknown colours shown black: ${[...unknownColours].join(', ')}.`);
    if (!authoredSteps) warnings.push('This model has no authored build steps. Showing its parts and subassemblies as supplied.');
    if (warnings.length) status(warnings.join(' '), 'warning');
    else status('New parts are shown in colour; earlier parts are grey. Use ← / → to change steps.');
  }
  function render() { if (renderer && camera) renderer.render(scene, camera); }

  function fitView() {
    if (!handler) return;
    const [position, rotation] = handler.computeCameraPositionRotation(new THREE.Matrix4(), new THREE.Matrix4(), true);
    root.position.copy(position);
    root.setRotationFromMatrix(rotation);
    root.updateMatrixWorld(true);
    const bounds = handler.getAccumulatedBounds().clone().applyMatrix4(root.matrixWorld);
    if (bounds.isEmpty()) throw new Error('The current step has no visible geometry.');
    const size = Math.max(bounds.getSize(new THREE.Vector3()).length(), 10);
    camera.position.set(size, size * .8, size);
    camera.up.set(0, 1, 0);
    controls.target.set(0, 0, 0);
    camera.zoom = 1;
    camera.near = .1;
    camera.far = Math.max(size * 10, 1000);
    const aspect = Math.max($('stage').clientWidth, 1) / Math.max($('stage').clientHeight, 1);
    const halfHeight = size * .6 / Math.min(aspect, 1);
    camera.left = -halfHeight * aspect;
    camera.right = halfHeight * aspect;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
    camera.updateProjectionMatrix();
    controls.update();
    render();
  }

  function showParts() {
    const step = handler.getCurrentStep();
    const [part] = handler.getCurrentStepInfo();
    const multiplier = handler.getMultiplierOfCurrentStep();
    $('assembly').textContent = `${part.modelDescription || part.ID}${multiplier > 1 ? ` · Build ×${multiplier}` : ''}`;
    $('parts-list').replaceChildren();
    pli.createClickMap(step);
    for (const icon of pli.clickMap) {
      const li = document.createElement('li');
      const canvas = document.createElement('canvas');
      canvas.width = 152; canvas.height = 128;
      canvas.setAttribute('aria-hidden', 'true');
      // Use PLIBuilder's geometry and framing with one reusable renderer.
      // Its renderIcon creates a new postprocessing target for every icon;
      // these small previews only need the normal instruction materials.
      const part = pli.getPartType(icon.partID);
      part.pliMC.overwriteColor(icon.c);
      part.pliMC.draw(false);
      pli.scene.add(part.mesh);
      iconRenderer.setSize(152, 128);
      pli.updateCamera(part.dx, part.dy);
      iconRenderer.render(pli.scene, pli.camera);
      canvas.getContext('2d').drawImage(iconRenderer.domElement, 0, 0, 152, 128);
      pli.scene.remove(part.mesh);
      const detail = document.createElement('div');
      detail.className = 'part-name';
      const quantity = document.createElement('strong');
      quantity.textContent = `${icon.mult} × ${icon.desc || icon.partID}`;
      const colour = document.createElement('small');
      colour.textContent = `${icon.partID.replace(/^pli_/, '')} · ${(LDR.Colors[icon.c]?.name || `Colour ${icon.c}`).replaceAll('_', ' ')}`;
      detail.append(quantity, colour);
      li.append(canvas, detail);
      $('parts-list').append(li);
    }
    if (!pli.clickMap.length) {
      const item = document.createElement('li');
      item.textContent = 'No additional parts in this step.';
      $('parts-list').append(item);
    }
  }

  function update() {
    const current = handler.getCurrentStepIndex();
    $('step').value = current;
    $('step').max = handler.totalNumberOfSteps;
    $('total').textContent = `of ${handler.totalNumberOfSteps}`;
    $('previous').disabled = handler.isAtFirstStep();
    $('next').disabled = handler.isAtLastStep();
    $('step').disabled = $('home').disabled = false;
    showParts();
    fitView();
    showStatus();
    const url = new URL(location.href);
    url.searchParams.set('step', current);
    // Keep an independently opened tab bookmarkable without adding history for
    // every step or changing the parent app's navigation.
    history.replaceState(null, '', url);
  }
  function goTo(value) {
    if (!loaded || failed) return;
    const n = Number(value);
    if (!Number.isInteger(n)) { $('step').value = handler.getCurrentStepIndex(); return; }
    try {
      handler.moveTo(Math.max(1, Math.min(n, handler.totalNumberOfSteps)));
      update();
    } catch (error) { fail(error); }
  }
  $('previous').addEventListener('click', () => goTo(handler.getCurrentStepIndex() - 1));
  $('next').addEventListener('click', () => goTo(handler.getCurrentStepIndex() + 1));
  $('step').addEventListener('change', event => goTo(event.target.value));
  $('home').addEventListener('click', fitView);
  addEventListener('keydown', event => {
    if (!loaded || failed || event.altKey || event.ctrlKey || event.metaKey || /INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) return;
    const destinations = { ArrowLeft: handler.getCurrentStepIndex() - 1, ArrowRight: handler.getCurrentStepIndex() + 1, Home: 1, End: handler.totalNumberOfSteps };
    if (event.key in destinations) { event.preventDefault(); goTo(destinations[event.key]); }
  });

  function onLoaded() {
    if (loaded || failed) return;
    try {
      const main = loader.getMainModel();
      if (!main || !main.steps.length) throw new Error('The model contains no buildable parts.');
      loader.substituteReplacementParts();
      loader.setReferencedFrom();
      const manager = {
        ldrLoader: loader,
        opaqueObject: new THREE.Group(), sixteenObject: new THREE.Group(), transObject: new THREE.Group(),
        // Old-part shading comes from MeshCollector. An outline postprocessor
        // is unnecessary when old parts have a distinct neutral colour.
        resetSelectedObjects() {}, hasSelectedObject() { return true; }, addSelectedObject() {},
      };
      root.add(manager.opaqueObject, manager.sixteenObject, manager.transObject);
      const part = new THREE.LDRPartDescription(16, new THREE.Vector3(), new THREE.Matrix3(), loader.mainModel, false);
      handler = new LDR.StepHandler(manager, [part], true);
      pli = new LDR.PLIBuilder(loader, false, loader.mainModel, document.createElement('canvas'), iconRenderer);
      handler.nextStep(false);
      loaded = true;
      const count = params.has('parts') ? Number(params.get('parts')) : main.countParts(loader);
      if (Number.isFinite(count) && count >= 0) $('parts').textContent = `${count.toLocaleString()} parts`;
      goTo(Number(params.get('step')) || 1);
      loader.loadTexmaps();
    } catch (error) { fail(error); }
  }

  async function start() {
    const source = params.get('model');
    if (!source) throw new Error('No model given. Add ?model=<URL of an .ldr or .mpd file>.');
    const modelUrl = new URL(source, location.href);
    if (modelUrl.origin !== location.origin) throw new Error('Choose a model from this app.');
    const fileName = decodeURIComponent(modelUrl.pathname.split('/').pop());
    $('file').textContent = fileName;
    document.title = `${fileName} · Build instructions`;
    const download = new URL(modelUrl);
    download.searchParams.set('download', '1');
    $('download').href = download.href;
    $('download').hidden = false;

    if (!window.THREE || !window.LDR?.StepHandler || !LDR.PLIBuilder) throw new Error('The buildinginstructions.js viewer assets are unavailable.');
    renderer = new THREE.WebGLRenderer({ canvas: $('model-canvas'), antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    renderer.setClearColor(0xf2f5f8);
    iconRenderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    iconRenderer.setPixelRatio(1);
    scene = new THREE.Scene();
    root = new THREE.Group();
    scene.add(root);
    camera = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 1000000);
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.screenSpacePanning = true;
    controls.addEventListener('change', render);
    const resize = new ResizeObserver(() => {
      renderer.setSize(Math.max($('stage').clientWidth, 1), Math.max($('stage').clientHeight, 1), false);
      if (loaded && !failed) fitView();
    });
    resize.observe($('stage'));
    addEventListener('pagehide', event => {
      if (event.persisted) return;
      resize.disconnect();
      controls.dispose();
      renderer.dispose();
      iconRenderer.dispose();
    });

    LDR.Options.showOldColors = 3;
    LDR.Options.lineContrast = 1;
    LDR.Colors.canBeOld = true;
    LDR.Colors.envMapPrefix = 'vendor/ldbi/textures/cube/';
    LDR.Colors.textureMaterialPrefix = 'vendor/ldbi/textures/materials/';
    // The pinned loader's unknown-colour warning references undefined locals.
    const parseColor = THREE.LDRLoader.prototype.parseColor;
    THREE.LDRLoader.prototype.parseColor = function (id) {
      if (!/^0x2[\da-f]{6}$/i.test(id) && LDR.Colors[id] === undefined) { unknownColours.add(id); return 0; }
      return parseColor.call(this, id);
    };
    await new Promise((resolve, reject) => LDR.Colors.load(resolve, () => reject(new Error('Could not load the LDraw colour definitions.')), '/ldraw/LDConfig.ldr'));
    // The pinned shaders take the old-part colour from colour 16, rather than
    // Options.oldColor. Set it before any shaders or materials are generated.
    LDR.Colors[16].value = 0xb9c2cb;
    LDR.Colors[16].edge = 0x758394;
    LDR.Studs.makeGenerators('', LDR.Options.studHighContrast, LDR.Options.studLogo);
    loader = new THREE.LDRLoader(onLoaded, null, {
      idToUrl: id => {
        const path = id.replaceAll('\\', '/').split('/').map(encodeURIComponent).join('/');
        return /\.(ldr|mpd)$/i.test(id) ? [new URL(path, modelUrl).href, `/ldraw-id/${path}`] : [`/ldraw-id/${path}`];
      },
      idToTextureUrl: id => `/ldraw/parts/textures/${id.toLowerCase().split('/').map(encodeURIComponent).join('/')}`,
      onProgress: () => { if (!loaded && !failed) status(`Loading parts… ${Object.keys(loader.partTypes).length}`); else if (loaded) render(); },
      onWarning: () => {},
      onError: error => { missing.add(error.subModel || 'unknown part'); if (loaded) showStatus(); },
    });
    // Fetch the source explicitly: a missing top-level model must be an error,
    // not the placeholder box the upstream loader creates for missing parts.
    const response = await fetch(modelUrl);
    if (!response.ok) throw new Error(`Could not fetch ${fileName} (HTTP ${response.status}).`);
    const text = await response.text();
    if (!/^[1-5]\s/m.test(text)) throw new Error('The model contains no LDraw geometry.');
    authoredSteps = /^0\s+(STEP|ROTSTEP)(?:\s|$)/m.test(text);
    // Hold completion while parsing the root, including fully inlined MPDs.
    loader.unloadedFiles++;
    loader.parse(text, fileName.toLowerCase());
    loader.unloadedFiles--;
    loader.reportProgress(loader.mainModel);
  }
  start().catch(fail);
})();
