import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(() => {
  const plugins = [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'masked-icon.svg'],
      manifest: {
        name: 'Text2SQL Agent',
        short_name: 'Text2SQL',
        description: 'Intelligent Text-to-SQL Assistant with Reasoning',
        theme_color: '#ffffff',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' }
        ]
      },
      workbox: { maximumFileSizeToCacheInBytes: 4000000 }
    })
  ]
  try {
    const { visualizer } = require('vite-plugin-visualizer')
    plugins.push(visualizer({ filename: 'dist/stats.html', gzipSize: true, brotliSize: true }))
  } catch (_) {}
  return {
    plugins
  }
})
