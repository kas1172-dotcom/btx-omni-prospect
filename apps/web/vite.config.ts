import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readBuildIdentity } from './build/identity.mjs'

const identity = readBuildIdentity()
const identityJson = JSON.stringify(identity)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), {
    name: 'btx-release-identity',
    generateBundle() { this.emitFile({ type: 'asset', fileName: 'build.json', source: identityJson }) },
    configureServer(server) {
      server.middlewares.use('/build.json', (_request, response) => {
        response.setHeader('Content-Type', 'application/json')
        response.setHeader('Cache-Control', 'no-store')
        response.end(identityJson)
      })
    },
  }],
  define: { __BTX_BUILD__: identityJson },
  server: {
    proxy: {
      '/api': process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
})
