# Deferred connected dependencies

The release configuration deploys the governed **SAMPLE** POC only. `BTX_DATA_MODE=CONNECTED` never falls back to SAMPLE and remains unavailable until these dependencies are explicitly configured and approved:

- PRISM/PowerBI account, BU, monthly/detail field and access confirmation.
- Paperless Parts read access and account/quote field confirmation.
- BTX HubSpot production read/write access and ownership conventions.
- Okta/enterprise SSO (development auth remains the POC mode).
- Approved live public-source credentials and collector configuration.
- Overdue-order activation after order-level promised-date/status fields are confirmed.

Production secrets are supplied through the platform environment: `DATABASE_URL` (or `BTX_DATABASE_URL`) and `BTX_FRONTEND_ORIGINS`. No secrets belong in this repository.
