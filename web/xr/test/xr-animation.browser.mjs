// XR_TEST_URL=http://localhost:4173 PLAYWRIGHT_CHANNEL=chrome npm run test:xr
// Run against `npm run dev -- --port 4173` or a backend with the current XR build.
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import { animatedGlb, quantizedGlb } from './fixtures/animated-glb.mjs';

const baseURL = process.env.XR_TEST_URL ?? 'http://localhost:8765';
let browser;
before(async () => {
  browser = await chromium.launch({
    channel: process.env.PLAYWRIGHT_CHANNEL,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
  });
});
after(async () => browser?.close());

async function open(t, body, collection = '/files/generated/') {
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    // IWER has no real-room hit testing; the app uses its existing floor fallback.
    if (message.type() === 'error' && !message.text().includes('Synthethic Environment Module')) errors.push(message.text());
  });
  t.after(async () => { await page.close(); assert.deepEqual(errors, []); });
  await page.route('**/api/glb?**', route => route.fulfill({ contentType: 'model/gltf-binary', body }));
  await page.goto(`${baseURL}/xr/?model=${encodeURIComponent(collection + 'animation-test.mpd')}&emulate=quest3`);
  await page.waitForFunction(() => window.xrApp?.menu() || document.querySelector('#status.error'));
  assert.equal(await page.locator('#status').textContent(), 'Ready');
  await page.locator('#enter').click();
  await page.waitForFunction(() => window.xrApp?.world.session);
  // Placement waits for three real XR frames (shader compilation can delay them).
  await page.waitForFunction(() => Math.abs(xrApp.placed.holder.position.y -
    (xrApp.world.camera.getWorldPosition(xrApp.placed.holder.position.clone()).y - 0.55)) < 0.02);
  return page;
}

const toggle = page => page.evaluate(() => xrApp.menu().getElementById('animation').dispatchEvent({ type: 'click' }));
const state = page => page.evaluate(() => {
  const { model, placed } = xrApp;
  const menu = xrApp.menu();
  return {
    time: model.animation?.mixer.time,
    playing: model.animation?.playing,
    rigid: model.root.getObjectByName('moving')?.position.x,
    morph: model.root.getObjectByName('morph')?.morphTargetInfluences[0],
    bone: model.root.getObjectByName('tip')?.quaternion.z,
    holder: [placed.holder.position.toArray(), placed.holder.quaternion.toArray(), placed.holder.scale.toArray()],
    button: menu.getElementById('animation').properties.value.display,
    label: menu.getElementById('animation-label').properties.value.text,
    playIcon: menu.getElementById('animation-play').properties.value.display,
    pauseIcon: menu.getElementById('animation-pause').properties.value.display,
  };
});

for (const [collection, quantized] of [['/files/generated/', false], ['/gallery-files/', true]]) {
  test(`VR Play/Pause, pose, manipulation and session lifecycle: ${collection}`, async t => {
    const page = await open(t, await (quantized ? quantizedGlb() : animatedGlb()), collection);
    const initial = await state(page);
    assert.equal(initial.button, 'flex');
    assert.equal(initial.label, 'Play');
    assert.equal(initial.playing, false);
    await page.waitForTimeout(150);
    assert.deepEqual(await state(page), initial, 'starts paused');
    await toggle(page);
    await page.waitForFunction(() => xrApp.model.animation.mixer.time > 0.2);
    const playing = await state(page);
    assert.ok(playing.rigid > initial.rigid && playing.morph > initial.morph && playing.bone > initial.bone);
    assert.equal(playing.label, 'Pause');
    assert.equal(playing.playIcon, 'none');
    assert.equal(playing.pauseIcon, 'flex');
    assert.deepEqual(playing.holder, initial.holder, 'playback does not move the placement');
    await page.evaluate(() => {
      xrApp.placed.scaleBy(1.2);
      xrApp.placed.turn(0.4);
      xrApp.placed.holder.position.x += 0.1;
    });
    const transformed = await state(page);
    await page.waitForFunction(time => xrApp.model.animation.mixer.time > time + 0.1, transformed.time);
    assert.deepEqual((await state(page)).holder, transformed.holder);
    await toggle(page);
    const paused = await state(page);
    await page.waitForTimeout(150);
    assert.deepEqual(await state(page), paused);
    assert.equal(paused.label, 'Play');
    assert.equal(paused.playIcon, 'flex');
    assert.equal(paused.pauseIcon, 'none');
    assert.ok(await page.evaluate(() => {
      const { model, placed, world } = xrApp;
      placed.recenter(world.camera);
      const center = model.bounds.getCenter(placed.holder.position.clone()).add(model.root.position);
      const target = world.camera.getWorldPosition(center.clone()).addScaledVector(world.camera.getWorldDirection(center.clone()), 0.75);
      return placed.holder.localToWorld(center).distanceTo(target) < 1e-6;
    }), 'recenter tracks the animated centre');
    await toggle(page);
    await page.waitForFunction(time => xrApp.model.animation.mixer.time > time + 0.1, paused.time);
    await page.evaluate(() => xrApp.world.exitXR());
    await page.waitForFunction(() => !xrApp.model.animation.playing && !xrApp.world.session);
    const exited = await state(page);
    await page.waitForTimeout(150);
    assert.equal((await state(page)).time, exited.time);
    assert.equal(exited.label, 'Play');
    await page.locator('#enter').click();
    await page.waitForFunction(() => !!xrApp.world.session);
    assert.equal((await state(page)).time, exited.time, 're-entry keeps the paused pose');
  });
}

test('static GLBs keep batching and do not offer playback', async t => {
  const page = await open(t, await animatedGlb(false));
  assert.equal((await state(page)).button, 'none');
  assert.ok(await page.evaluate(() => !xrApp.model.animation && xrApp.model.batches.length > 0));
});

for (const path of (process.env.GLB_TEST_FILES ?? '').split(':').filter(Boolean)) {
  test(`plays compressed animations in XR: ${path}`, async t => {
    const page = await open(t, await readFile(path));
    const size = await page.evaluate(() => xrApp.model.bounds.getSize(xrApp.placed.holder.position.clone()).toArray());
    assert.ok(size.every(v => Number.isFinite(v) && v >= 0) && size.some(v => v > 0));
    await toggle(page);
    await page.waitForFunction(() => xrApp.model.animation.mixer.time > 0.2);
    await toggle(page);
    assert.equal((await state(page)).playing, false);
  });
}
