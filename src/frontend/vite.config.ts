import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: '../',
  envPrefix: ['ENTRA_', 'RESOURCE_API_', 'FOUNDRY_'],
  server: {
    host: true,
  },
})
