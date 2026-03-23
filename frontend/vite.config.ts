import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Proxy all /api/* requests to the FastAPI backend (port 8000).
    // This covers every backend route: /api/health, /api/activity,
    // /api/export/download/{filename}, and all blueprint routers,
    // since they all share the /api prefix.
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
