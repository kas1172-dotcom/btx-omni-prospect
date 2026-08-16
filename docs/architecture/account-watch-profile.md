# Canonical account watch profile

A watch profile is governed account metadata used only for Stage A plausibility and entity resolution. It is not a source of facts and does not invent identifiers.

```text
AccountWatchProfile
  canonical_account_id (required)
  legal_name, display_name, aliases[], former_names[], subsidiaries[]
  domain, official_newsroom_url, investor_relations_url
  sec_cik?, uei?, cage?, source_native_identifiers{source: identifier}
  facilities[{canonical_facility_id?, name, geography}]
  programs/platforms[{canonical_program_id?, aliases[]}]
  industry_classifications[]
```

Identifiers are optional and may be populated only from governed Account data or verified source evidence. Parent/subsidiary relationships are resolution candidates, not automatic substitution. A profile records the source and verification date for each noncanonical field when persisted.
