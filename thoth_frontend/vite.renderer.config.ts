import { defineConfig } from 'vite';

// https://vitejs.dev/config
export default defineConfig({
  define: {
    __VITE_BACKEND_URL__: JSON.stringify(process.env.VITE_BACKEND_URL || 'https://thoth-510062880720.asia-south2.run.app')
  }
});
