import { defineConfig } from 'vite'

export default defineConfig(({ command }) => ({
  // GitHub Pages のサブパス配下でも動くよう相対パスで出す
  base: command === 'build' ? './' : '/',
  build: {
    outDir: '../app',
    emptyOutDir: true,
    // pmtiles が最上位 await を含むため ES2022 が必要
    target: 'es2022',
  },
  // maplibre のワーカーは ESM のまま出す(main.ts の setWorkerUrl を参照)
  worker: { format: 'es' },
  server: {
    port: 5176,
    strictPort: true,
    // Windows 上のファイルを WSL 側から見る構成ではファイル変更イベントが届かないため
    watch: { usePolling: true, interval: 300 },
  },
  define: {
    __BUILD_TIME__: JSON.stringify(new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC'),
  },
}))
