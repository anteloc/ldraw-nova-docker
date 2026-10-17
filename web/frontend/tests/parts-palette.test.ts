import assert from "node:assert/strict";
import { afterEach, mock, test } from "node:test";
import { api } from "../src/api.ts";

afterEach(() => mock.restoreAll());

for (const extension of ["ldr", "csv", "xml", "io"]) {
  test(`uploads ${extension} bytes without altering binary data and returns canonical CSV`, async () => {
    const bytes = new Uint8Array([0, 255, 128, 80, 75, ...new Uint8Array(70_000).fill(42)]);
    const file = new File([bytes], `palette.${extension}`);
    const canonical = { csv: "part_id,color_id,max_quantity\n3001,4,2\n", enabled: true, allowed_combinations: 1 };
    mock.method(globalThis, "fetch", async (url: string, options: RequestInit) => {
      assert.equal(url, "/api/parts-palette/import");
      assert.equal(options.method, "POST");
      const body = JSON.parse(options.body as string);
      assert.equal(body.filename, file.name);
      assert.deepEqual(new Uint8Array(Buffer.from(body.data_base64, "base64")), bytes);
      return new Response(JSON.stringify(canonical), { headers: { "Content-Type": "application/json" } });
    });
    assert.deepEqual(await api.importPalette(file), canonical);
  });
}

test("invalid imports surface the server error without saving a chat palette", async () => {
  const calls: string[] = [];
  mock.method(globalThis, "fetch", async (url: string) => {
    calls.push(url);
    return new Response(JSON.stringify({ detail: "Missing submodel" }), { status: 400 });
  });
  await assert.rejects(api.importPalette(new File(["bad"], "bad.ldr")), /Missing submodel/);
  assert.deepEqual(calls, ["/api/parts-palette/import"]);
});
