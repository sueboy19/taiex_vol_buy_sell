import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";
const wsTarget = proxyTarget.replace(/^http/, "ws");

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": proxyTarget,
      "/ws": { target: wsTarget, ws: true },
    },
  },
});
