import { type ModelFile, type InventoryReport } from "./api";
export type Lot = {
  id: string;
  part: string | null;
  color: number | null;
  quantity: number;
  raw_part: string;
  raw_color: string;
  system: string;
  label: string;
};
export type Color = { code: number; name: string; hex: string };
export type Catalog = {
  ready: boolean;
  sets: number;
  updated: string | null;
  building: boolean;
  stage: string;
  error: string | null;
  warning?: string | null;
};
export type Stock = {
  lots: Lot[];
  palette: Color[];
  total: number;
  usable: number;
  unmapped: number;
  catalog?: Catalog;
};
export type SetItem = {
  num: string;
  name: string;
  year: number;
  num_parts: number;
  lego_url: string;
  bricklink_url: string;
};
export type FitReport = InventoryReport;
export function trackParts(
  event: string,
  properties: Record<string, string | number | boolean> = {},
) {
  (
    window as Window & {
      posthog?: { capture: (event: string, properties: object) => void };
    }
  ).posthog?.capture(event, properties);
}
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch("/api/my-parts" + path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "Parts request failed. Please retry.",
    );
  }
  return response.json();
}
const json = (method: string, body: object): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const inventoryApi = {
  read: () => call<Stock>(""),
  search: (query: string) =>
    call<{ sets: SetItem[]; catalog: Catalog }>(
      "/sets?query=" + encodeURIComponent(query),
    ),
  catalog: () => call<Catalog>("/catalog", { method: "POST" }),
  importUrl: (url: string, system: string, copies: number) =>
    call<Stock>("/import-url", json("POST", { url, system, copies })),
  upload: (file: File, system: string) =>
    call<Stock>(
      "/upload?system=" +
        encodeURIComponent(system) +
        "&label=" +
        encodeURIComponent(file.name.slice(0, 80)),
      {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      },
    ),
  add: (part: string, color: number, quantity: number) =>
    call<Stock>("/lots", json("POST", { part, color, quantity })),
  edit: (id: string, part: string, color: number, quantity: number) =>
    call<Stock>(
      "/lots/" + encodeURIComponent(id),
      json("PUT", { part, color, quantity }),
    ),
  find: (query: string) =>
    call<{ parts: { id: string; description: string }[] }>(
      "/find?query=" + encodeURIComponent(query),
    ),
  async fit(file: string) {
    const { revision } = await call<{ revision: string }>(
      "/revision?file=" + encodeURIComponent(file),
    );
    return call<{ model: ModelFile; chat_id: string; report: FitReport }>(
      "/fit",
      json("POST", { file, revision }),
    );
  },
};
