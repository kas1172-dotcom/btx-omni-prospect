# Phase 20 — Roles, Settings, and Cross-App Governance

The product has two backend-authorized roles: **Salesperson** and **Manager**. Salespeople can work within their permitted Customer and Action scope; Managers additionally approve governed work, assign ownership, and review team-visible Actions. Browser visibility is explanatory only: the API enforces protected mutations and never trusts a browser role preference.

Settings separates durable personal preferences from system-managed configuration. It shows the authenticated role, permitted capabilities, and safe provider status without credentials or raw provider failures. Statuses retain their meaning: `SAMPLE` is not connected data, `CONNECTED` is live governed availability, `NOT_CONFIGURED` requires deployment configuration, and `UNAVAILABLE` is a bounded runtime state.

Development role simulation uses the server-side development principal tokens only. It is not production identity, SSO, directory synchronization, or a client-side elevation mechanism. Future enterprise identity integration must map an authenticated server principal to these bounded roles before any authorized context is assembled for Actions or Omni.

Seller-facing language uses Customer, Prospect, and Customers & Prospects. Internal API and persistence symbols may retain `account` where a rename would create migration or compatibility risk.
