# Phase 16 — External Intelligence

External Intelligence is the seller-facing projection of governed Signal Briefs. It answers what changed, why it matters, which canonical Customer or Prospect is affected, and where the supporting evidence can be reviewed.

`Today's Priority Signals` preserves backend `priority_briefing` order. The Intelligence Feed presents the brief headline, Customer link, seller summary, and a prominent **Why it matters** block directly from `why_it_may_matter`; it does not calculate a score or generate new commercial meaning in the browser. Evidence disclosure includes source, evidence references, publication/collection time, and the relevant event time when supplied. A governed recommended action can take the seller to the existing internal Actions lifecycle; it never creates work automatically.

The four context tiles distinguish public intelligence, SAMPLE BTX commercial context, CRM/contact state, and quote/RFQ state. Provider state is displayed as supplied: unavailable and not configured are never presented as zero or connected.

The tracked-target rail uses the command-center's system-recommended, read-only watch projection. It reports governed activity language such as `New signal context`, never fabricated price-style percentage movement.

Search and filters work over the projected Signal Brief fields and combine Customer, canonical market, source, and timing. Priority is the default backend order; the other visible sorts only reorder the already-projected set for a seller-selected view.

Forward Radar uses only backend briefs with a future `relevant_event_timestamp`. Records without a supported future event date are excluded; a publication timestamp is never substituted.

Federal Procurement remains the separate Phase 15 drill-down, available alongside Intelligence Monitor. Its Active Opportunities and Awarded Dollars views are unchanged.

Known limitation: this POC's general Intelligence endpoint does not yet expose server-side query parameters, so the loaded governed projection is filtered in the UI. Ranking, eligibility, association, freshness, evidence, and Radar eligibility remain backend authoritative.
