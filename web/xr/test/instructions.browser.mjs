// Run against a backend with the current frontend/viewer and Docker's pinned assets:
// VIEWER_TEST_URL=http://localhost:8765 PLAYWRIGHT_CHANNEL=chrome npm run test:instructions
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright';

const baseURL = process.env.VIEWER_TEST_URL ?? 'http://localhost:8765';
const modelPath = '/gallery-files/instructions test.mpd';
const brick = (colour, x, y, name = '3001.dat') => `1 ${colour} ${x} ${y} 0 1 0 0 0 1 0 0 0 1 ${name}`;
const model = [
  '0 FILE main.ldr', '0 Instruction test', brick(4, 0, 0), brick(4, 80, 0), '0 STEP',
  brick(14, 0, -24, 'assembly.ldr'), brick(14, 80, -24, 'assembly.ldr'), '0 ROTSTEP 0 90 0 REL',
  brick(2, 0, -72, '3020.dat'), '0 FILE assembly.ldr', '0 Test subassembly',
  brick(16, 0, 0), '0 STEP', brick(1, 0, -24), '',
].join('\n');
let browser;
before(async () => {
  browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
});
after(async () => browser?.close());

async function pageFor(t, body = model, code = 200) {
  const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
  const errors = [], requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error' && /shader|WebGL/i.test(message.text())) errors.push(message.text()); });
  page.on('request', request => requests.push(request.url()));
  await page.route('**/instructions%20test.mpd*', route => route.fulfill({ status: code, contentType: 'text/plain', body }));
  t.after(async () => { await page.close(); assert.deepEqual(errors, []); });
  return { page, requests };
}
async function open(page, query = '') {
  await page.goto(`${baseURL}/viewer/instructions.html?model=${encodeURIComponent(modelPath)}${query}`);
  await ready(page);
}
async function ready(page) {
  await page.waitForFunction(() => !document.getElementById('step').disabled || document.getElementById('status').classList.contains('error'));
  assert.equal(await page.locator('#status').getAttribute('class'), '', await page.locator('#status').textContent());
}
async function changeStep(page, n) {
  await page.locator('#step').fill(String(n));
  await page.locator('#step').press('Enter');
  await page.locator('#step').blur();
}

test('authored steps, repeated subassemblies, parts, rotation and navigation', async t => {
  const { page, requests } = await pageFor(t);
  await open(page);
  assert.equal(await page.locator('#total').textContent(), 'of 5');
  assert.equal(await page.locator('#previous').isDisabled(), true);
  assert.match(await page.locator('#parts-list').textContent(), /2 × Brick\s+2 x\s+4/);
  const previewHasPixels = await page.locator('#parts-list canvas').first().evaluate(canvas =>
    canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data.some((n, i) => i % 4 === 3 && n > 0));
  assert.ok(previewHasPixels, 'part preview contains rendered geometry');
  const firstView = await page.locator('#model-canvas').screenshot();
  await page.locator('#next').click();
  assert.equal(await page.locator('#step').inputValue(), '2');
  assert.match(await page.locator('#assembly').textContent(), /Build ×2/);
  assert.match(await page.locator('#parts-list').textContent(), /Yellow/);
  assert.notDeepEqual(await page.locator('#model-canvas').screenshot(), firstView);
  await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('#step').inputValue(), '3');
  assert.match(await page.locator('#parts-list').textContent(), /Blue/);
  const stepImage = await page.locator('#model-canvas').screenshot();
  const greyPixels = await page.evaluate(async source => {
    const image = new Image(); image.src = source; await image.decode();
    const canvas = document.createElement('canvas');
    canvas.width = image.width; canvas.height = image.height;
    const context = canvas.getContext('2d'); context.drawImage(image, 0, 0);
    const rgba = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let i = 0; i < rgba.length; i += 4) {
      if (Math.abs(rgba[i] - 185) < 8 && Math.abs(rgba[i + 1] - 194) < 8 && Math.abs(rgba[i + 2] - 203) < 8) count++;
    }
    return count;
  }, `data:image/png;base64,${stepImage.toString('base64')}`);
  assert.ok(greyPixels > 50, 'previously added parts render grey');
  await page.locator('#next').click();
  assert.equal(await page.locator('#step').inputValue(), '4');
  assert.match(await page.locator('#parts-list').textContent(), /2 × Test subassembly/);
  await changeStep(page, 5);
  assert.equal(await page.locator('#next').isDisabled(), true);
  assert.match(await page.locator('#parts-list').textContent(), /3020.dat/);
  assert.ok(!requests.some(url => url.includes('/api/glb')), 'instructions always use the authored LDraw source');
  assert.equal(new URL(page.url()).searchParams.get('step'), '5');
  await page.keyboard.press('Home');
  assert.equal(await page.locator('#step').inputValue(), '1');
  assert.deepEqual(await page.locator('#model-canvas').screenshot(), firstView);
  await changeStep(page, 9999);
  assert.equal(await page.locator('#step').inputValue(), '5');
  await page.reload();
  await ready(page);
  assert.equal(await page.locator('#step').inputValue(), '5', 'bookmark restores the step');
});

test('models without steps show a notice and cannot advance past the only step', async t => {
  const { page } = await pageFor(t, `0 Simple model\n${brick(4, 0, 0)}\n`);
  await page.goto(`${baseURL}/viewer/instructions.html?model=${encodeURIComponent(modelPath)}`);
  await page.waitForFunction(() => !document.getElementById('home').disabled);
  assert.match(await page.locator('#status').textContent(), /no authored build steps/);
  assert.equal(await page.locator('#total').textContent(), 'of 1');
  assert.equal(await page.locator('#previous').isDisabled(), true);
  assert.equal(await page.locator('#next').isDisabled(), true);
});

test('missing source, empty geometry and missing model parameter show errors', async t => {
  for (const [body, code, message] of [['Not found', 404, /HTTP 404/], ['0 Empty\n', 200, /no LDraw geometry/]]) {
    const { page } = await pageFor(t, body, code);
    await page.goto(`${baseURL}/viewer/instructions.html?model=${encodeURIComponent(modelPath)}`);
    await page.waitForFunction(() => document.getElementById('status').classList.contains('error'));
    assert.match(await page.locator('#status').textContent(), message);
    assert.equal(await page.locator('#next').isDisabled(), true);
  }
  const { page } = await pageFor(t);
  await page.goto(`${baseURL}/viewer/instructions.html`);
  await page.waitForFunction(() => document.getElementById('status').classList.contains('error'));
  assert.match(await page.locator('#status').textContent(), /No model given/);
});

test('missing parts and unknown colours are reported while the model remains usable', async t => {
  const { page } = await pageFor(t, `0 Missing part\n${brick(987654, 0, 0)}\n0 STEP\n${brick(4, 80, 0, 'nonexistent-test-part.dat')}\n`);
  await page.route('**/ldraw-id/nonexistent-test-part.dat', route => route.fulfill({ status: 404, body: 'Not found' }));
  await page.goto(`${baseURL}/viewer/instructions.html?model=${encodeURIComponent(modelPath)}`);
  await page.waitForFunction(() => !document.getElementById('home').disabled);
  assert.match(await page.locator('#status').textContent(), /Missing parts shown as boxes/);
  assert.match(await page.locator('#status').textContent(), /Unknown colours shown black: 987654/);
  await page.locator('#next').click();
  assert.equal(await page.locator('#step').inputValue(), '2');
});

test('gallery, My Models and chat cards open instructions, switch modes, and fit on mobile', async t => {
  const { page } = await pageFor(t);
  const card = {
    id: 'test-model', file: 'instructions test.mpd', name: 'Test model', description: 'Instruction test',
    model_url: modelPath, parts: 7, status: 'ready', bom_status: 'ready', mtime: 1, created_at: 1, warnings: [],
  };
  const chat = { id: 'instructions-chat', title: 'Instructions chat', llm_model_id: null, running: false, created_at: 1, updated_at: 1 };
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    const json = path === '/api/chats' ? { chats: [chat] }
      : path === '/api/llm-models' ? { models: [], default_id: null }
      : path === '/api/chats/instructions-chat' ? { chat, messages: [{ id: 1, role: 'assistant', content: 'Built the model.', created_at: 1, _models: ['test-model'] }], models: { 'test-model': card } }
      : { models: [card, { ...card, id: 'deleted', file: 'deleted.mpd', model_url: null }], pending: 0 };
    return route.fulfill({ json });
  });
  for (const path of ['/gallery', '/models', '/chat/instructions-chat']) {
    card.model_url = path === '/gallery' ? modelPath : modelPath.replace('/gallery-files/', '/files/generated/');
    await page.goto(baseURL + path);
    const button = page.getByRole('button', { name: 'Build instructions', exact: true }).first();
    await button.click();
    const dialog = page.getByRole('dialog');
    assert.match(await dialog.getAttribute('aria-label'), /Build instructions of Instruction test/);
    const frame = page.frameLocator('iframe');
    await frame.locator('#next:enabled').waitFor();
    assert.match(await dialog.getByText('Open in new tab').getAttribute('href'), /instructions\.html\?model=.*&parts=7/);
    await dialog.getByRole('button', { name: '3D view', exact: true }).click();
    assert.match(await page.locator('iframe').getAttribute('src'), /\/viewer\/viewer\.html/);
    await dialog.getByRole('button', { name: '3D player', exact: true }).click();
    assert.match(await page.locator('iframe').getAttribute('src'), /\/viewer\/player\.html/);
    await dialog.getByRole('button', { name: 'Build instructions', exact: true }).click();
    await frame.locator('#next:enabled').waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const child = page.frames().find(f => f.url().includes('instructions.html'));
    assert.ok(await child.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.ok((await frame.locator('#model-canvas').boundingBox()).height > 150);
    await dialog.getByRole('button', { name: 'Close', exact: true }).click();
    await page.setViewportSize({ width: 1200, height: 800 });
    if (path !== '/chat/instructions-chat') assert.equal(await page.locator('.model-card').last().getByRole('button', { name: 'Build instructions' }).isDisabled(), true);
  }
});
