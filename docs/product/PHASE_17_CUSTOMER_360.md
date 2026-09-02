# Phase 17 — Customer 360

Customer 360 is keyed only by a canonical Customer or Prospect ID.  The backend
projection composes bounded commercial, quote, order, CRM, program, component,
capability, facility, and canonically linked intelligence records for that one
identity.

Commercial providers expose both `data_mode` and `source_state`.  `SAMPLE` is
explicitly simulated BTX context; `CONNECTED` may coexist with it for public
intelligence. `NO_LINKED_DATA`, `NOT_CONFIGURED`, and `UNAVAILABLE` are shown as
missing states, never as numeric zero.

Customers may have SAMPLE commercial context. Prospects may instead have no
commercial or CRM records while still showing governed program/component/
capability relevance. HUXWRX is the regression example for that behavior.

The projection reuses Customer Attractiveness, Signal Brief, Relationship
Intelligence, and Actions authority. It does not change their algorithms,
create external writes, infer identities from public text, or represent live
internal integrations. Future live providers should implement the existing
provider-neutral state contract before their data is displayed as connected.
