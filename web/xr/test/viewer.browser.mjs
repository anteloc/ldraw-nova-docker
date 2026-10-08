// Run against a backend with the current viewer and Docker's vendored assets:
// VIEWER_TEST_URL=http://localhost:8765 npm run test:viewer
// PLAYWRIGHT_CHANNEL=chrome uses an installed Chrome instead of downloaded Chromium.
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import { animatedGlb, quantizedGlb } from './fixtures/animated-glb.mjs';

const baseURL = process.env.VIEWER_TEST_URL ?? 'http://localhost:8765';
let browser, animated, staticModel;
const mpd = '0 FILE browser-test.ldr\n0 Browser test brick\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n';

before(async () => {
  [animated, staticModel] = await Promise.all([animatedGlb(), animatedGlb(false)]);
  browser = await chromium.launch({
    channel: process.env.PLAYWRIGHT_CHANNEL,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
});
after(async () => browser?.close());

async function open(t, body = animated, collection = '/files/generated/', player = false) {
  const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
  const errors = [], requests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && /shader|WebGL/i.test(m.text())) errors.push(m.text()); });
  page.on('request', r => requests.push(r.url()));
  t.after(async () => { await page.close(); assert.deepEqual(errors, []); });
  await page.route('**/api/glb?**', r => body === null
    ? r.fulfill({ status: 404, json: { detail: 'no sibling GLB' } })
    : r.fulfill({ contentType: 'model/gltf-binary', body }));
  await page.route('**/browser-test.mpd*', r => r.fulfill({ contentType: 'text/plain', body: mpd }));
  const source = collection + 'browser-test.mpd';
  await page.goto(`${baseURL}/viewer/${player ? 'player' : 'viewer'}.html?model=${encodeURIComponent(source)}`);
  return { page, requests, source };
}

async function ready(page) {
  await page.waitForFunction(() => !document.getElementById('home').disabled || document.getElementById('status').classList.contains('error'));
  assert.equal(await page.locator('#status').evaluate(e => e.classList.contains('error')), false,
    await page.locator('#status').textContent());
}

const snapshot = page => page.evaluate(() => ({
  time: scene.mixer.time, moving: scene.root.getObjectByName('moving').position.x,
  morph: scene.root.getObjectByName('morph').morphTargetInfluences[0],
  bone: scene.root.getObjectByName('tip').quaternion.z,
  camera: scene.camera.position.toArray(),
}));

for (const collection of ['/files/generated/', '/gallery-files/']) {
  test(`GLB animation, rendering and camera controls: ${collection}`, async t => {
    const { page, requests, source } = await open(t, animated, collection);
    await ready(page);
    assert.ok(await page.locator('#animation').isVisible());
    assert.equal(await page.locator('#animation').getAttribute('aria-pressed'), 'false');
    assert.ok(!requests.some(url => new URL(url).pathname.endsWith('.mpd')), 'the alternate does not load MPD geometry');
    assert.ok(requests.some(url => new URL(url).searchParams.get('existing_only') === 'true'));
    assert.ok((await page.locator('#download').getAttribute('href')).startsWith(source));
    const start = await snapshot(page);
    await page.waitForTimeout(150);
    assert.deepEqual(await snapshot(page), start, 'starts paused');
    await page.locator('#animation').click();
    for (const mode of ['normal', 'poly', 'high']) {
      const before = await snapshot(page);
      await page.locator(`[data-mode=${mode}]`).click();
      await page.waitForFunction(time => scene.mixer.time > time + 0.1, before.time);
      const after = await snapshot(page);
      assert.ok(after.moving > before.moving && after.morph > before.morph && after.bone > before.bone);
      assert.deepEqual(after.camera, start.camera, 'mode switches preserve the view');
      const materials = await page.evaluate(() => ({
        wireframe: scene.meshes.every(({object}) => object.material.wireframe),
        authored: scene.meshes.every(({object,material}) => object.material === material),
        edges: scene.lines.some(({object}) => object.visible),
        shadows: scene.renderer.shadowMap.enabled,
      }));
      assert.equal(materials.wireframe, mode === 'poly');
      assert.equal(materials.authored, mode === 'high');
      assert.equal(materials.edges, mode !== 'poly');
      assert.equal(materials.shadows, mode === 'high');
    }
    await page.locator('#animation').click();
    const paused = await snapshot(page);
    await page.waitForTimeout(150);
    assert.deepEqual(await snapshot(page), paused);
    await page.locator('[data-mode=poly]').click();
    assert.deepEqual(await snapshot(page), paused, 'quality change preserves the paused pose');
    await page.locator('#animation').click();
    await page.waitForFunction(time => scene.mixer.time > time + 0.1, paused.time);
    await page.locator('#animation').click();
    await page.locator('[data-camera=walk]').click();
    await page.keyboard.down('KeyW');
    await page.waitForTimeout(200);
    await page.keyboard.up('KeyW');
    assert.notDeepEqual((await snapshot(page)).camera, start.camera);
    await page.locator('[data-camera=inspect]').click();
    await page.locator('#home').click();
    assert.ok(await page.evaluate(() =>
      scene.orbitControls.target.distanceTo(scene.getBounds().getCenter(new THREE.Vector3())) < 1e-6),
    'reset frames the current animated pose');
  });
}

test('GLB without clips hides playback; its original PBR values survive mode switches', async t => {
  const { page } = await open(t, staticModel);
  await ready(page);
  assert.equal(await page.locator('#animation').isVisible(), false);
  await page.locator('[data-mode=normal]').click();
  await page.locator('[data-mode=high]').click();
  assert.deepEqual(await page.evaluate(() => {
    const m = scene.meshes[0].object.material;
    return [m.roughness, m.metalness];
  }), [0.72, 0.23]);
});

test('quantized skin/morph attributes frame the visible model at its actual size', async t => {
  const { page } = await open(t, await quantizedGlb());
  await ready(page);
  const size = await page.evaluate(() => scene.getBounds().getSize(new THREE.Vector3()).divideScalar(2500).toArray());
  assert.ok(size.every((v, i) => Math.abs(v - [0.52, 0.24, 0.12][i]) < 0.001), JSON.stringify(size));
  await page.locator('[data-mode=poly]').click();
  await page.locator('#animation').click();
  await page.waitForFunction(() => scene.mixer.time > 0.1);
  const pose = await snapshot(page);
  assert.ok(pose.moving > 0 && pose.morph > 0 && pose.bone > 0);
});

test('missing sibling retains the MPD viewer and every rendering mode', async t => {
  const { page, requests } = await open(t, null);
  await ready(page);
  assert.equal(await page.evaluate(() => !!scene.isGLB), false);
  assert.equal(await page.locator('#animation').isVisible(), false);
  for (const mode of ['normal', 'poly', 'high']) {
    await page.locator(`[data-mode=${mode}]`).click();
    await ready(page);
  }
  assert.ok(requests.some(url => new URL(url).pathname.endsWith('.mpd')));
  assert.equal(requests.filter(url => new URL(url).pathname === '/api/glb').length, 1);
});

test('a malformed canonical GLB reports an error instead of silently showing MPD', async t => {
  const { page, requests } = await open(t, Buffer.from('broken GLB'));
  await page.waitForFunction(() => document.getElementById('status').classList.contains('error'));
  assert.equal(await page.locator('#animation').isVisible(), false);
  assert.ok(!requests.some(url => new URL(url).pathname.endsWith('.mpd')));
});

test('the player requests MPD even when an animated sibling is available', async t => {
  const { page, requests } = await open(t, animated, '/gallery-files/', true);
  if (!requests.some(url => new URL(url).pathname.endsWith('.mpd'))) {
    await page.waitForRequest(request => new URL(request.url()).pathname.endsWith('.mpd'));
  }
  assert.ok(!requests.some(url => new URL(url).pathname === '/api/glb'));
});

// Optional externally generated assets (e.g. Draco and Meshopt exports).
for (const path of (process.env.GLB_TEST_FILES ?? '').split(':').filter(Boolean)) {
  test(`loads compressed/exported GLB: ${path}`, async t => {
    const { page } = await open(t, await readFile(path));
    await ready(page);
    for (const mode of ['normal', 'poly', 'high']) {
      await page.locator(`[data-mode=${mode}]`).click();
      await ready(page);
      if (await page.locator('#animation').isVisible()) {
        const time = await page.evaluate(() => scene.mixer.time);
        await page.locator('#animation').click();
        await page.waitForFunction(time => scene.mixer.time > time + 0.1, time);
        await page.locator('#animation').click();
      }
    }
  });
}
