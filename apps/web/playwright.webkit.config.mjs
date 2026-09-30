import base from './playwright.config.mjs'
import { defineConfig } from '@playwright/test'

// Chromium runs the complete deterministic suite. WebKit retains the browser-
// sensitive compatibility surface: navigation, responsive layouts, forms,
// drawers/modals, Map, Actions, Communications, Omni/chat, relationships,
// Today, shared filters, and shell behavior.
export default defineConfig({
  ...base,
  testMatch: [
    'navigation.spec.mjs',
    'shared-shell.spec.mjs',
    'customer-experience-core.spec.mjs',
    'map-v2.spec.mjs',
    'map-details.spec.mjs',
    'actions-v2.spec.mjs',
    'editor-independent-loading.spec.mjs',
    'communications-settings.spec.mjs',
    'communication-stale-version.spec.mjs',
    'omni-chat-v2.spec.mjs',
    'omni-phase6.spec.mjs',
    'relationship-commercial-scenes.spec.mjs',
    'relationship-intelligence.spec.mjs',
    'opportunities-rebuild.spec.mjs',
    'profile-ux-refinement.spec.mjs',
    'final-release-convergence.spec.mjs',
    'wave4-visual.spec.mjs',
    'shared-filters.spec.mjs',
    'today-reference.spec.mjs',
    'today-validation-lanes.spec.mjs',
    'seller-scenarios.spec.mjs',
    'suggestion-feedback.spec.mjs',
  ],
})
