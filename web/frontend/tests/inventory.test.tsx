import { browser } from "./setup";
import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import MyParts from "../src/pages/MyParts";
import UseMyParts from "../src/components/UseMyParts";
import Composer from "../src/components/Composer";
import { AppContext, type AppState } from "../src/context";
import { inventoryApi, type Stock, type FitReport } from "../src/inventory";
import type { ModelFile, TurnOptions } from "../src/api";

let root: Root | undefined;
const originalFetch = globalThis.fetch;
const originalApi = { ...inventoryApi };
const events: { event: string; properties: object }[] = [];
(browser as any).posthog = {
  capture: (event: string, properties: object) =>
    events.push({ event, properties }),
};
const stock: Stock = {
  lots: [],
  palette: [
    { code: 4, name: "Red", hex: "#FF0000" },
    { code: 1, name: "Blue", hex: "#0000FF" },
  ],
  total: 0,
  usable: 0,
  unmapped: 0,
  catalog: {
    ready: true,
    sets: 28000,
    updated: "2026-10-03",
    building: false,
    stage: "Ready",
    error: null,
  },
};
const model = {
  file: "source.mpd",
  name: "source",
  description: "Source model",
  model_url: "/files/generated/source.mpd",
  gallery: false,
} as ModelFile;
const report: FitReport = {
  total_parts: 4,
  matched_parts: 3,
  missing_parts: 1,
  color_changes: 1,
  splits: 1,
  missing: [{ part: "3001", color: 4, quantity: 1 }],
};
const state: AppState = {
  chats: [],
  chatsLoaded: true,
  refreshChats() {},
  llms: [],
  defaultLlmId: null,
  refreshLlms() {},
  openViewer() {},
};
async function mount(element: React.ReactNode, context = state) {
  document.body.innerHTML = '<div id="root"></div>';
  root = createRoot(document.getElementById("root")!);
  await act(async () =>
    root!.render(
      <MemoryRouter>
        <AppContext.Provider value={context}>{element}</AppContext.Provider>
      </MemoryRouter>,
    ),
  );
}
async function click(text: string) {
  const button = [...document.querySelectorAll("button")].find(
    (el) => el.textContent === text,
  );
  assert.ok(button, `Missing button ${text}`);
  await act(async () => button.click());
}
async function input(label: string, value: string) {
  const el = document.querySelector(
    `[aria-label="${label}"]`,
  ) as HTMLInputElement;
  assert.ok(el);
  const proto =
    el.tagName === "TEXTAREA"
      ? browser.HTMLTextAreaElement.prototype
      : browser.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(el, value);
  await act(async () => {
    el.dispatchEvent(new browser.Event("input", { bubbles: true }));
    el.dispatchEvent(new browser.Event("change", { bubbles: true }));
  });
}
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  globalThis.fetch = originalFetch;
  Object.assign(inventoryApi, originalApi);
  events.length = 0;
});

test("fit API captures revision, encodes filenames and rejects a stale source", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  globalThis.fetch = (async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response(
      JSON.stringify(
        calls.length === 1
          ? { revision: "abc" }
          : { detail: "Model changed. Refresh My Models and try again." },
      ),
      { status: calls.length === 1 ? 200 : 409 },
    );
  }) as typeof fetch;
  await assert.rejects(inventoryApi.fit("red & blue.mpd"), /Model changed/);
  assert.equal(
    calls[0].url,
    "/api/my-parts/revision?file=red%20%26%20blue.mpd",
  );
  assert.deepEqual(JSON.parse(String(calls[1].init?.body)), {
    file: "red & blue.mpd",
    revision: "abc",
  });
});

test("empty inventory and set search provide source links and copy-aware imports", async () => {
  inventoryApi.read = async () => structuredClone(stock);
  inventoryApi.search = async () => ({
    sets: [
      {
        num: "10696-1",
        name: "Creative Brick Box",
        year: 2015,
        num_parts: 484,
        lego_url:
          "https://www.lego.com/en-us/service/building-instructions/10696",
        bricklink_url:
          "https://www.bricklink.com/v2/catalog/catalogitem.page?S=10696-1",
      },
    ],
    catalog: stock.catalog!,
  });
  let imported: unknown;
  inventoryApi.importUrl = async (...args) => {
    imported = args;
    return { ...stock, total: 968, usable: 900 };
  };
  await mount(<MyParts />);
  assert.match(document.body.textContent!, /No owned parts yet/);
  await input("Search LEGO sets", "10696");
  await input("Set copies", "2");
  await act(async () =>
    document
      .querySelector("form")!
      .dispatchEvent(
        new browser.Event("submit", { bubbles: true, cancelable: true }),
      ),
  );
  assert.ok(
    document.querySelector(
      'a[href="https://www.bricklink.com/v2/catalog/catalogitem.page?S=10696-1"]',
    ),
  );
  await click("Add set");
  assert.deepEqual(imported, ["10696-1", "rebrickable", 2]);
  assert.match(document.body.textContent!, /968/);
  assert.ok(events.some((e) => e.event === "inventory_set_search"));
  assert.ok(!JSON.stringify(events).includes("10696"));
});

test("unmapped lots stay visible and can be corrected without silently counting stock", async () => {
  inventoryApi.read = async () => ({
    ...stock,
    total: 5,
    unmapped: 1,
    lots: [
      {
        id: "id",
        part: null,
        color: null,
        quantity: 5,
        raw_part: "printed-x",
        raw_color: "999",
        system: "bricklink",
        label: "Owned set",
      },
    ],
  });
  let edited: unknown;
  inventoryApi.edit = async (...args) => {
    edited = args;
    return { ...stock, total: 5, usable: 5 };
  };
  await mount(<MyParts />);
  assert.match(document.body.textContent!, /Needs LDraw mapping/);
  await click("Map lot");
  await input("Map to LDraw part", "3001");
  const select = document.querySelector(
    '[aria-label="Map to LDraw color"]',
  ) as HTMLSelectElement;
  await act(async () => {
    select.value = "4";
    select.dispatchEvent(new browser.Event("change", { bubbles: true }));
  });
  await click("Save lot");
  assert.deepEqual(edited, ["id", "3001", 4, 5]);
  assert.match(document.body.textContent!, /Updated the owned lot/);
});

test("fit action disables duplicate submission, reports shortages and opens saved version", async () => {
  let resolve: (value: any) => void = () => {};
  inventoryApi.fit = () => new Promise((r) => (resolve = r));
  let opened: unknown,
    refreshed = 0;
  await mount(<UseMyParts model={model} />, {
    ...state,
    refreshChats() {
      refreshed++;
    },
    openViewer(target) {
      opened = target;
    },
  });
  await click("Use my parts");
  assert.equal(document.querySelector("button")!.disabled, true);
  assert.match(document.body.textContent!, /original stays saved/);
  await act(async () =>
    resolve({
      model: {
        ...model,
        file: "fitted-v1.mpd",
        model_url: "/files/generated/fitted-v1.mpd",
      },
      chat_id: "id",
      report,
    }),
  );
  assert.match(document.body.textContent!, /3 of 4 pieces owned · 1 missing/);
  assert.match(document.body.textContent!, /1 × 3001/);
  await click("View fitted model");
  assert.equal((opened as any).modelUrl, "/files/generated/fitted-v1.mpd");
  assert.equal(refreshed, 1);
  assert.ok(events.some((e) => e.event === "inventory_model_fit_completed"));
});

test("fit errors allow retry and saved reports survive page reload", async () => {
  inventoryApi.fit = async () => {
    throw new Error("Add usable inventory in My Parts first");
  };
  await mount(<UseMyParts model={{ ...model, inventory_report: report }} />);
  assert.match(document.body.textContent!, /1 missing/);
  await click("Use my parts");
  assert.match(
    document.querySelector('[role="alert"]')!.textContent!,
    /Add usable inventory/,
  );
  assert.equal(document.querySelector("button")!.disabled, false);
  assert.equal(document.querySelector("a")!.getAttribute("href"), "/parts");
});

test("use-my-parts checkbox reaches turn options", async () => {
  const llm = {
    id: "demo",
    model_name: "Demo",
    litellm_params: { model: "openai/demo" },
    profile: {
      efforts: [],
      context_budgets: [],
      context_window: null,
      default_effort: null,
    },
  } as any;
  let sent: TurnOptions | undefined;
  await mount(
    <Composer
      llmId="demo"
      onLlmChange={() => {}}
      running={false}
      onSend={(_text, options) => {
        sent = options;
      }}
    />,
    { ...state, llms: [llm] },
  );
  const checkbox = document.querySelector(
    'input[type="checkbox"]',
  ) as HTMLInputElement;
  await act(async () => checkbox.click());
  assert.equal(checkbox.checked, true);
  await input("Message", "Build a tower with my pieces");
  await act(async () =>
    document
      .querySelector("form")!
      .dispatchEvent(
        new browser.Event("submit", { bubbles: true, cancelable: true }),
      ),
  );
  assert.equal(sent?.use_my_parts, true);
  assert.deepEqual(
    events.find((e) => e.event === "inventory_mode_changed")?.properties,
    { enabled: true },
  );
});

test("parts search suggests installed IDs and excludes descriptions from analytics", async () => {
  inventoryApi.read = async () => structuredClone(stock);
  const searches: string[] = [];
  inventoryApi.find = async (query) => {
    searches.push(query);
    return { parts: [{ id: "3001.dat", description: "Brick 2 x 4" }] };
  };
  await mount(<MyParts />);
  await input("Loose part number", "brick 2 x 4");
  await act(async () => new Promise((resolve) => setTimeout(resolve, 350)));
  assert.deepEqual(searches, ["brick 2 x 4"]);
  assert.equal(
    document.querySelector("datalist option")!.getAttribute("value"),
    "3001",
  );
  assert.ok(!JSON.stringify(events).includes("brick 2 x 4"));
});

test("oversized uploads are rejected before sending any parts data", async () => {
  inventoryApi.read = async () => structuredClone(stock);
  let called = false;
  inventoryApi.upload = async () => {
    called = true;
    return stock;
  };
  await mount(<MyParts />);
  const file = new browser.File(
    ["x".repeat(2 * 1024 * 1024 + 1)],
    "oversized.csv",
  );
  const element = document.querySelector(
    '[aria-label="Parts list file"]',
  ) as HTMLInputElement;
  Object.defineProperty(element, "files", {
    value: [file],
    configurable: true,
  });
  await act(async () =>
    element.dispatchEvent(new browser.Event("change", { bubbles: true })),
  );
  assert.equal(called, false);
  assert.match(
    document.querySelector('[role="alert"]')!.textContent!,
    /exceeds 2 MB/,
  );
});

test("mapping an unknown color requires an explicit choice instead of assuming black", async () => {
  inventoryApi.read = async () => ({
    ...stock,
    total: 1,
    unmapped: 1,
    lots: [
      {
        id: "unmapped",
        part: "3001",
        color: null,
        quantity: 1,
        raw_part: "3001",
        raw_color: "999",
        system: "bricklink",
        label: "Uploaded",
      },
    ],
  });
  let edited = false;
  inventoryApi.edit = async () => {
    edited = true;
    return stock;
  };
  await mount(<MyParts />);
  await click("Map lot");
  assert.equal(
    (
      document.querySelector(
        '[aria-label="Map to LDraw color"]',
      ) as HTMLSelectElement
    ).value,
    "",
  );
  await click("Save lot");
  assert.equal(edited, false);
  assert.match(
    document.querySelector('[role="alert"]')!.textContent!,
    /Choose the LDraw color/,
  );
});

test("a saved fitting report disappears when the backend invalidates its model revision", async () => {
  await mount(<UseMyParts model={{ ...model, inventory_report: report }} />);
  assert.match(document.body.textContent!, /1 missing/);
  await act(async () =>
    root!.render(
      <MemoryRouter>
        <AppContext.Provider value={state}>
          <UseMyParts model={{ ...model, inventory_report: null }} />
        </AppContext.Provider>
      </MemoryRouter>,
    ),
  );
  assert.ok(!document.body.textContent!.includes("1 missing"));
});
