import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base so the build works at any GitHub Pages path
// (https://<user>.github.io/<repo>/) without knowing the repo name.
export default defineConfig({
  plugins: [react()],
  base: './',
})
