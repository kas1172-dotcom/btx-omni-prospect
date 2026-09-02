# Phase 15 — Federal Procurement Intelligence

Federal Procurement is a read-only Intelligence workspace. SAM.gov is the forward opportunity pipeline; USAspending supplies historical award context. Source observations remain authoritative and the API projects typed procurement fields rather than exposing source payloads to the browser.

SAM fields are normalized only from official structured fields: notice type, Sources Sought classification, set-aside, deadline, NAICS, agency and evidence. `BTX_MONITOR_SAM_NAICS` is applied only while its verification state is `VERIFIED`; otherwise the UI says targeting is pending confirmation.

USAspending's existing recipient-targeted monitor enrichment is unchanged. The projection supports typed award amounts, action-date-derived fiscal year/quarter, recipient, agency, award ID, NAICS when supplied, and aggregate quarterly/top-recipient results. Totals are provisional unless verified procurement scope exists.

Federal Opportunity Relevance is a separate draft 0–100 deterministic rubric, not Customer Attractiveness or PWin. Verified NAICS fit is worth 40, official notice stage 15, deadline actionability 10, and governed BTX commercial context 35 when available. The product labels it “Draft relevance model — pending BTX calibration.” Missing context earns no points; urgency cannot outrank strong fit by itself. No Gemini, embeddings, or probability semantics are used.

Monitor source versions durably preserve each canonical source record's `first_seen_at` and `last_seen_at`. The API uses fixed rolling seven-day boundaries to report current and newly observed counts. It reports a numeric period-over-period delta only when a real comparable baseline exists; otherwise the UI says **History unavailable**. No synthetic live baseline is created. Deterministic browser fixtures are explicitly `SAMPLE` and are isolated from CONNECTED source behavior. Award records currently lack governed downstream delivery or milestone dates, so supply-chain lag is explicitly insufficient history. Future calibration requires BTX-approved NAICS, capability/program mappings, and governed commercial associations.
