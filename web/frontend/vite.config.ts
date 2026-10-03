import process from "node:process";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the UI with hot reload and forwards everything else to
// the backend running in the container (docker compose up -d).
const backend = process.env.LDRAW_NOVA_API_URL || "http://localhost:8765"; // LDRAW_NOVA_WEB_PORT in docker-compose.yml

export default defineConfig({
  plugins: [react()],
  server: {
    // Keep the browser Host so the backend's same-origin check also works in dev.
    proxy: Object.fromEntries(["/api", "/files", "/gallery-files", "/demo", "/ref", "/ldraw", "/ldraw-id", "/viewer", "/xr"].map((p) => [p, { target: backend, changeOrigin: false }])),
  },
});
