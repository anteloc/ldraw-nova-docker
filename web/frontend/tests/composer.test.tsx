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
  await act(async () => root.render(<MemoryRouter><AppContext.Provider value={state}>
    <Composer llmId="test" onLlmChange={() => {}} onSend={async (...args) => { sent.push(args); }}
      running={running} initialText="A fox statue" initialOptions={initialOptions} />
  </AppContext.Provider></MemoryRouter>));
  return { element, sent, async close() { await act(async () => root.unmount()); element.remove(); } };
}

test("default prompt stays unchanged; optional sculpture choice is submitted and reversible", async () => {
  const mounted = await mount();
  const checkbox = mounted.element.querySelector('input[type="checkbox"]') as HTMLInputElement;
  assert.equal(checkbox.checked, false);
  await act(async () => checkbox.click());
  assert.equal(checkbox.checked, true);
  await act(async () => mounted.element.querySelector("form")!.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true })));
  assert.equal(mounted.sent[0][0], "A fox statue");
  assert.equal(mounted.sent[0][1].build_style, "sculpture");
  await act(async () => checkbox.click());
  assert.equal(checkbox.checked, false);
  await mounted.close();
});

test("saved sculpture choice returns checked and cannot change during generation", async () => {
  const mounted = await mount({ mode: "agent", permissions: "ask", build_style: "sculpture" }, true);
  const checkbox = mounted.element.querySelector('input[type="checkbox"]') as HTMLInputElement;
  assert.equal(checkbox.checked, true);
  assert.equal(checkbox.disabled, true);
  await act(async () => checkbox.click());
  assert.equal(checkbox.checked, true);
  await mounted.close();
});
