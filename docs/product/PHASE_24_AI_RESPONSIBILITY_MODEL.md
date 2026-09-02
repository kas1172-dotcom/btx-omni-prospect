# Phase 24 AI responsibility model

Phase 24 uses Gemini for bounded language and public-research work. It does not delegate governed business decisions to a model.

## Gemini responsibilities

- Natural-language intent interpretation for closed read routes.
- Cited public-web research through server-side Google Search grounding.
- Public technical extraction and component-candidate decomposition.
- Seller-facing explanations of deterministic results.
- Conversational synthesis using governed context and cited public findings.
- Seller-language communication and internal-note proposals.

Web pages, public findings, prior conversation, and supplied labels are content rather than instructions. They cannot request writes, reveal secrets, or override this boundary.

## Deterministic Omni responsibilities

- Canonical identity and referent resolution.
- Evidence and provenance authority.
- Customer and Federal scoring, ranking, eligibility, and map geography.
- Controlled component/capability matching and BTX Business Unit mapping.
- Relationship graph traversal and validation.
- Roles, authorization, Action lifecycle, communication approval, and delivery state.

Public research becomes cited evidence candidate content. It cannot create a canonical Customer, internal commercial fact, controlled taxonomy record, relationship edge, Action, or completed workflow state.

## Governed drafting

Drafting receives a bounded `GovernedDraftingRequest`: Customer display context, explicit seller instruction, supplied deterministic facts, supplied evidence IDs, optional existing draft text, and explicitly supplied cited public findings. Gemini can return only a subject, body, and an evidence-ID subset of that request.

The application returns a proposal. The seller must review it and explicitly save it through the existing draft workflow. Gemini cannot select recipients, approve, send, or claim an external write. Provider failure returns editable manual text and leaves the existing draft/workflow untouched.

## Phase boundaries

Phase 24D provides cited public research and Phase 24E provides governed drafting. Neither phase redesigns scoring, matching, relationships, Maps, roles, Actions, or delivery. Public-search reliability and connected BTX data remain explicit limitations.
