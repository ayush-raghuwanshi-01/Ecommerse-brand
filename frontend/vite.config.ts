import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Dev server proxies `/api` and `/static` to the FastAPI backend so the browser
 * only ever talks to one origin (CORS-free, and works behind preview tunnels).
 *
 * Configure via `frontend/.env`:
 *   VITE_DEV_PROXY_TARGET  – backend origin          (default http://127.0.0.1:8000)
 *   VITE_DEV_ALLOWED_HOSTS – extra hosts to accept   (comma separated)
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000';
  const allowedHosts = (env.VITE_DEV_ALLOWED_HOSTS || '')
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean);

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: Number(env.VITE_DEV_PORT) || 5173,
      strictPort: false,
      // `true` accepts any host (tunnels, container preview domains). Narrow it
      // with VITE_DEV_ALLOWED_HOSTS if you want an explicit allow-list.
      allowedHosts: allowedHosts.length > 0 ? allowedHosts : true,
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: false },
        '/static': { target: proxyTarget, changeOrigin: false },
      },
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
      allowedHosts: allowedHosts.length > 0 ? allowedHosts : true,
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: false },
        '/static': { target: proxyTarget, changeOrigin: false },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
    },
  };
});
