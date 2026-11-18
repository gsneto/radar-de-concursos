import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('framer-motion')) return 'vendor-motion';
          if (id.includes('@tanstack/react-query')) return 'vendor-query';
          if (id.includes('lucide-react') || id.includes('cmdk') || id.includes('@radix-ui')) {
            return 'vendor-ui';
          }
          if (
            id.includes('/react/') ||
            id.includes('/react-dom/') ||
            id.includes('/react-router') ||
            id.includes('\\react\\') ||
            id.includes('\\react-dom\\') ||
            id.includes('\\react-router')
          ) {
            return 'vendor-react';
          }
          return undefined;
        },
      },
    },
  },
});
