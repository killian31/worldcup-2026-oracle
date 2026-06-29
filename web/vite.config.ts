import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Builds the static shell into ../docs (GitHub Pages root). emptyOutDir:false so
// the Python-managed docs/data/*.json is preserved; assets land in docs/assets
// with hashed filenames for automatic cache-busting.
export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  build: { outDir: '../docs', emptyOutDir: false, assetsDir: 'assets' },
})
