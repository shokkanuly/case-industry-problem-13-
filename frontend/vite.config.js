import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import basicSsl from '@vitejs/plugin-basic-ssl'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    basicSsl() // Generates a self-signed SSL certificate so mobile getUserMedia works over LAN
  ],
  server: {
    host: true,         // Expose to LAN (phone can reach laptop IP)
    port: 5174,
    https: true,        // Force HTTPS context for camera security permission
  }
})
