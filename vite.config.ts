import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Bound to 0.0.0.0 so the dev server is reachable from outside the sandbox
// (the Arena preview proxies to it). No backend, so no proxy rules needed.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // The Arena preview reaches the dev server through a *.e2b.app host, which
    // Vite's host-check would otherwise reject with a 403.
    allowedHosts: [".e2b.app", "localhost"],
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    allowedHosts: [".e2b.app", "localhost"],
  },
  build: {
    // three.js + @react-three/drei land in one chunk by design: HeroCanvas is a
    // lazy import, so the 3D payload is only fetched when the hero mounts and
    // never blocks first paint. The warning is expected, not a regression.
    chunkSizeWarningLimit: 950,
  },
});
