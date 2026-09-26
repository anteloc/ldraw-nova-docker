import { defineConfig } from "vitest/config";

// The mixed-reality viewer, served by the backend at /xr/.
// `npm run dev` serves it with hot reload and forwards the model routes to the
// backend running in the container (docker compose up -d); add ?emulate=quest3
// to try it without a headset.
const backend = "http://localhost:8765"; // LEOCAD_WEB_PORT in docker-compose.yml

export default defineConfig({
  base: "/xr/",
  server: {
    proxy: Object.fromEntries(["/api", "/files", "/ref"].map((p) => [p, backend])),
  },
  build: { target: "esnext", sourcemap: false },
  // One three.js for the app and IWSDK: both resolve `three` to super-three.
  // uikit is deduped too, or panels fail instanceof checks (IWSDK template note).
  resolve: { dedupe: ["three", "@pmndrs/uikit", "@pmndrs/uikit-horizon", "@pmndrs/uikit-lucide"] },
  optimizeDeps: { exclude: ["@babylonjs/havok"] },
  test: { environment: "node" },
});
