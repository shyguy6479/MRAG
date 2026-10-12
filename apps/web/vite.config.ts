import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'MRAG_');
  const backend = loadEnv(mode, '../..', 'ATLAS_');
  return {
    plugins: [react()],
    server: { proxy: {
      '/api': {
        target: env.MRAG_DEV_API_URL || 'http://127.0.0.1:8000',
        // Dev-server headers stay on Node; Vite never exposes ATLAS_* to the bundle.
        headers: backend.ATLAS_API_KEY ? { 'X-API-Key': backend.ATLAS_API_KEY } : undefined,
        rewrite: path => path.replace(/^\/api/, '')
      }
    }}
  };
});
