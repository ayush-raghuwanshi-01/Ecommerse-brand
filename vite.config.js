import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Dev server proxies API + uploaded media to the FastAPI backend so the browser
// never talks to another origin (preview-friendly, CORS-free).
export default defineConfig({
    plugins: [react()],
    server: {
        host: '0.0.0.0',
        allowedHosts: ['.e2b.app'],
        proxy: {
            '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
            '/static': { target: 'http://127.0.0.1:8000', changeOrigin: false },
        },
    },
    build: {
        rollupOptions: {
            output: { manualChunks: { three: ['three', '@react-three/fiber', '@react-three/drei'] } },
        },
    },
});
