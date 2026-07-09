import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,         // Expose to LAN (phone can reach laptop IP)
    port: 5174,
    // historyApiFallback: true is built-in for Vite dev server —
    // all routes including /phone serve index.html automatically
  }
})
