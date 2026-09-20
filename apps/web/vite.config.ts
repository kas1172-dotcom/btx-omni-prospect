import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readBuildIdentity } from './build/identity.mjs'

const identity = readBuildIdentity()
const identityJson = JSON.stringify(identity)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), {
    name: 'btx-release-identity',
    generateBundle(_options, bundle) {
      this.emitFile({ type: 'asset', fileName: 'build.json', source: identityJson })
      const modules: Record<string, string> = {}
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== 'chunk' || !chunk.facadeModuleId) continue
        const match = chunk.facadeModuleId.match(/\/features\/(?:accounts|map|actions|communications|intelligence|monitor|settings)\/(\w+)\.tsx$/)
        if (match) modules[match[1]] = `/${chunk.fileName}`
      }
      // A same-build, code-only manifest makes recovery independent of browser
      // import-error wording. Never contains customer data or configuration secrets.
      this.emitFile({ type: 'asset', fileName: 'workspace-modules.json', source: JSON.stringify({ build: identity, modules }) })
    },
    configureServer(server) {
      server.middlewares.use('/build.json', (_request, response) => {
        response.setHeader('Content-Type', 'application/json')
        response.setHeader('Cache-Control', 'no-store')
        response.end(identityJson)
      })
    },
  }],
  define: {
    __BTX_BUILD__: identityJson,
    // Keep hosted cookies first-party, including when the Vercel project's
    // older environment configuration still names the Fly origin directly.
    ...(process.env.VERCEL === '1' ? { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api') } : {}),
  },
  server: {
    proxy: {
      '/api': process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
})
