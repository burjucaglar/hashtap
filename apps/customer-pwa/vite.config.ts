import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'HashTap',
        short_name: 'HashTap',
        description: 'QR sipariş ve ödeme',
        theme_color: '#0b2545',
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      '/hashtap': {
        target: 'http://localhost:8069',
        changeOrigin: true,
      },
    },
  },
});
