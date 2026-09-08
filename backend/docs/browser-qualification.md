# Browser qualification boundaries

The default `apps/web` command `npm run test:e2e` runs deterministic seller workflows against its own backend/frontend ports; it refuses to reuse an existing server. Before starting, use Python3.11 and Node22.14.0, PostgreSQL16 and the frozen locks. Create a disposable local database named `btx_omni_e2e*`, set its exact `BTX_DATABASE_URL`, run `uv run alembic upgrade head`, then `uv run python tests/prepare_e2e.py` from `backend`. Setup verifies origin and local destination; no deletion/reset, external CRM write or public fetch is performed. It imports the reviewed eleven-account runtime package and a checksum-pinned historical G.17 excerpt, then proves commercial replay. Do not run this fixture setup on a deployed database.

CI runs the same suite on Chromium and WebKit using Ubuntu24.04. Browser installation uses the existing locked Playwright package, not a new app dependency. Artifacts survive failed runs. A configured job is not evidence that it has executed or passed.

Separate REQUIRED release gates are not replaced by that fixture suite:

- `monitor-public-evidence.spec.mjs`: real durable public collection and retained passages. `E2E_BASE_URL=<verified URL> npx playwright test --config=playwright.live-evidence.config.mjs` runs without starting a fixture server. Authentication must use the deployed session policy; the test cannot disable it. The accepted target list is explicit. Fixture Monitor events cannot qualify this gate.
- `hosted-demo-access.spec.mjs`: the existing explicit production-mode SAMPLE session fixture; it tests the server-issued role boundary, not real deployed secure-cookie transport. Its HTTP-local cookie adjustment is test-only and cannot qualify hosted cookie security. Actual hosted sessions, CSRF and roles require separate live-browser evidence.
- Actual Google Maps renderer, real configured Gemini, fresh deployed Monitor/model calls, restart persistence, scheduler-triggered execution, performance and scope journeys remain live qualification gates. Test-mode Maps and deterministic Omni responses cannot qualify them.

Never turn an unavailable live gate into a passing fixture claim. Deployment remains gated by the complete requirement/test/evidence ledger, not by the deterministic CI job alone.
