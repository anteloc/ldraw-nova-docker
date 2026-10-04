import { Window } from "happy-dom";
export const browser = new Window({ url: "http://localhost:8766" });
for (const key of [
  "window",
  "document",
  "navigator",
  "HTMLElement",
  "HTMLInputElement",
  "HTMLTextAreaElement",
  "Event",
  "MouseEvent",
  "File",
  "FileReader",
  "localStorage",
])
  Object.defineProperty(globalThis, key, {
    value: key === "window" ? browser : (browser as any)[key],
    configurable: true,
  });
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
