# Public Facility, Geography and Official Feed Enrichment

**Historical input checkpoint.** The table below is not the current environment's coverage. See [generated catalog counts](SAMPLE_ENHANCEMENT_REPORT.md#generated-catalog-counts). The enhancement separately labels fictional coordinates; they are not verified public geography.

The supplied `docs/research/btx_public_facility_feed_enrichment.json` (schema 1.0) was validated against the 78-account researched universe by `research_account_id`. The loader rejects duplicate account rows, duplicate facility keys, invalid coordinate pairs, and unsupported schema versions.

| Coverage | Count |
| --- | ---: |
| researched accounts processed | 78 |
| verified public HQ coordinates | 29 |
| verified non-HQ facilities | 0 |
| accounts with public coordinates | 29 |
| official newsroom URLs | 40 |
| investor-relations URLs | 16 |
| official feed URLs | 13 |
| accounts without verified public geography | 49 |

The current input contains no verified non-HQ facilities, so multi-facility support is retained by the canonical `AccountFacility` contract but has no verified data rows yet. A verified HQ is represented as a public `AccountFacility` with `VERIFIED_PUBLIC_HQ`; any future verified facility uses `VERIFIED_PUBLIC_FACILITY`. Existing SAMPLE planning locations remain `SAMPLE_INTERNAL_LOCATION` and are never promoted to public pins.

Map rule: public pins use verified facility coordinates first, then verified HQ; accounts without either have no public pin. SAMPLE points remain separately labelled. Proximity remains seller-planning context only and is not an Account Attractiveness input.

Generic Monitor watch profiles now receive verified newsroom, IR, and feed URLs where supplied: 40 newsroom, 16 IR, and 13 feed endpoints. Missing feeds remain absent/unavailable; no company-specific collector or adapter was added. GE Aerospace was added as a verified public HQ from its SEC-reported Evendale, Ohio address, with coordinates returned by the U.S. Census Bureau Geocoder. Remaining gaps are verified non-HQ facility coverage, 49 public geographies, and publisher/feed coverage for the other researched accounts.
