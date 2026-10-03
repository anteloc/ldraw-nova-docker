import { Window } from "happy-dom";
import assert from "node:assert/strict";
import { test } from "node:test";

const window = new Window({ url: "http://localhost/" });
Object.assign(globalThis, { window, document: window.document, HTMLElement: window.HTMLElement,
  Event: window.Event, MouseEvent: window.MouseEvent, IS_REACT_ACT_ENVIRONMENT: true });
const React = await import("react");
const { act } = React;
const { createRoot } = await import("react-dom/client");
const { MemoryRouter } = await import("react-router-dom");
const { AppContext } = await import("../src/context");
const { default: Composer } = await import("../src/components/Composer");

async function mount(initialOptions?: any, running = false) {
  const element = document.createElement("div"); document.body.append(element);
  const root = createRoot(element);
  const sent: any[] = [];
  const state: any = { llms: [{ id: "test", name: "Test", litellm_params: { model: "test" },
    profile: { efforts: [], context_budgets: [] } }], chats: [], chatsLoaded: true,
    defaultLlmId: "test", refreshChats() {}, refreshLlms() {}, openViewer() {} };
  async function render(isRunning: boolean) { await act(async () => root.render(<MemoryRouter><AppContext.Provider value={state}>
    <Composer llmId="test" onLlmChange={() => {}} onSend={async (...args) => { sent.push(args); }}
      running={isRunning} initialText="A fox statue" initialOptions={initialOptions} />
  </AppContext.Provider></MemoryRouter>)); }
  await render(running);
  return { element, sent, render, async close() { await act(async () => root.unmount()); element.remove(); } };
}

function settingsTrigger(element: HTMLElement) {
  return element.querySelector('.additional-settings-trigger') as HTMLButtonElement;
}

async function openSettings(element: HTMLElement) {
  await act(async () => settingsTrigger(element).click());
  return document.querySelector('.additional-settings-panel input[type="checkbox"]') as HTMLInputElement;
}

test("ordinary generation submits without opting into sculpture", async () => {
  const mounted = await mount();
  await act(async () => mounted.element.querySelector("form")!.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  assert.equal(mounted.sent[0][0], "A fox statue");
  assert.equal(mounted.sent[0][1].build_style, undefined);
  await mounted.close();
});

test("default prompt stays unchanged; optional sculpture choice is submitted and reversible", async () => {
  const mounted = await mount();
  assert.equal(document.querySelector('.additional-settings-panel'), null);
  const checkbox = await openSettings(mounted.element);
  assert.equal(checkbox.checked, false);
  await act(async () => checkbox.click());
  assert.equal(checkbox.checked, true);
  await act(async () => mounted.element.querySelector("form")!.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  assert.equal(mounted.sent[0][0], "A fox statue");
  assert.equal(mounted.sent[0][1].build_style, "sculpture");
  const reopened = await openSettings(mounted.element);
  assert.equal(reopened.checked, true);
  await act(async () => reopened.click());
  assert.equal(reopened.checked, false);
  await mounted.close();
});

test("saved sculpture choice returns checked and cannot change during generation", async () => {
  const mounted = await mount({ mode: "agent", permissions: "ask", build_style: "sculpture" });
  const checkbox = await openSettings(mounted.element);
  assert.equal(checkbox.checked, true);
  await mounted.render(true);
  assert.equal(document.querySelector('.additional-settings-panel'), null);
  assert.equal(settingsTrigger(mounted.element).disabled, true);
  await act(async () => settingsTrigger(mounted.element).click());
  assert.equal(document.querySelector('.additional-settings-panel'), null);
  await mounted.render(false);
  assert.equal((await openSettings(mounted.element)).checked, true);
  await mounted.close();
});

test("settings dismiss with Escape, outside pointer and focus; Escape returns focus", async () => {
  const mounted = await mount();
  const checkbox = await openSettings(mounted.element);
  assert.equal(document.activeElement, checkbox);
  await act(async () => document.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
  assert.equal(document.querySelector('.additional-settings-panel'), null);
  assert.equal(document.activeElement, settingsTrigger(mounted.element));
  await openSettings(mounted.element);
  await act(async () => document.body.dispatchEvent(new window.PointerEvent("pointerdown", { bubbles: true })));
  assert.equal(document.querySelector('.additional-settings-panel'), null);
  await openSettings(mounted.element);
  await act(async () => (mounted.element.querySelector('textarea') as HTMLTextAreaElement).focus());
  assert.equal(settingsTrigger(mounted.element).getAttribute("aria-expanded"), "false");
  await mounted.close();
});

test("sculpture info shows an example and voxel-editor help on hover, focus and tap", async () => {
  const mounted = await mount();
  await openSettings(mounted.element);
  const info = document.querySelector('.sculpture-info-button') as HTMLButtonElement;
  assert.equal(document.querySelector('.sculpture-help'), null);
  await act(async () => info.dispatchEvent(new window.MouseEvent("mouseover", { bubbles: true })));
  const help = document.querySelector('.sculpture-help')!;
  assert.match(help.textContent!, /voxel editor.*voxel JSON/);
  assert.match(help.textContent!, /Estimated time: around 1–2 minutes for simple sculptures/);
  assert.match(help.querySelector('img')!.getAttribute('alt')!, /owl sculpture/);
  assert.match(help.querySelector('img')!.getAttribute('alt')!, /without a display base/);
  assert.ok(info.querySelector('svg[aria-hidden="true"]'));
  assert.equal((document.querySelector('.sculpture-option input') as HTMLInputElement).checked, false);
  assert.equal(info.getAttribute('aria-controls'), help.id);
  await act(async () => info.dispatchEvent(new window.MouseEvent("mouseout", { bubbles: true, relatedTarget: document.body })));
  assert.equal(document.querySelector('.sculpture-help'), null);
  await act(async () => info.focus());
  assert.equal(info.getAttribute('aria-expanded'), 'true');
  await act(async () => info.click());
  await act(async () => info.blur());
  assert.ok(document.querySelector('.sculpture-help'));
  await act(async () => info.click());
  assert.equal(document.querySelector('.sculpture-help'), null);
  await mounted.close();
});
