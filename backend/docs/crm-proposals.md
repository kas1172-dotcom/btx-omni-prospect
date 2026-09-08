# Governed local CRM proposals

`modules/work/crm_proposals.py` extends the existing Action repository and
HubSpot adapter boundary. Proposals, Manager decisions and attempts are immutable
`work_audit_events`; no second work database or live HubSpot client is introduced.
The old stateless auto-preview/execute methods have been removed.

`BTX_CRM_PROPOSAL_1` binds exact Action fields/version/fingerprint, canonical
commercial revision and existing scenario company/CRM-owner mapping. Local owner
and CRM owner are separate. Missing dates remain null; no portal ID or live
association is invented. Closed work, pending/rejected Action approval and missing
mapping block execution review. Proposal approval is separate and exact-version;
general Action approval alone is insufficient.

Authenticated routes under `/api/actions/{id}`:

- `POST /crm-preview`: `expected_version` saves/replays the exact proposal.
- `GET /crm-proposals`: saved proposals, decisions and attempts (latest100 events;
  earlier count disclosed). Existing Action authorization applies.
- `POST /crm-proposal-decision`: Manager, proposal ID, APPROVED/REJECTED and
  expected prior decision ID. No operation is executed by approval.
- `POST /crm-execute?confirmed=true`: Manager, exact proposal/current approval ID
  and retry key. The only permitted adapter is the existing local sample adapter.

PostgreSQL row locking serializes receipts with Action edits. SQLite qualification
uses an immediate transaction. Identical uncertain retries return their immutable
receipt; an explicit new retry after a confirmed failure receives a new attempt.
Successful proposals cannot duplicate the sample operation through another key.
There are at most50 proposals and50 attempts per Action in the bounded POC.
Commercial/mapping dependencies are reprojected at each request; locking against
concurrent cross-owner commercial import is still a separate integration concern.

Outcomes are `SAMPLE_COMPLETED`/`SAMPLE_FAILED`, always `external_write=false`.
They do not change Action status or represent actual HubSpot success. Real portal
mapping, external write authorization and live-adapter execution remain disabled;
this implementation is not proof of a live CRM integration. Historic legacy
`EXTERNAL_EXECUTED` events remain unchanged and retain their simulated metadata.
