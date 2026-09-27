import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the UI with hot reload and forwards everything else to
// the backend running in the container (docker compose up -d).
const backend = "http://localhost:8765"; // LDRAW_ASTRA_WEB_PORT in docker-compose.yml

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(["/api", "/files", "/ref", "/ldraw", "/ldraw-id", "/viewer"].map((p) => [p, backend])),
  },
});
