# SAMPLE fixture source-of-truth map

The authoritative runtime boundary is `backend/src/btx_omni/providers/sample/`.
SAMPLE startup calls `build_sample_environment()` and then, in SAMPLE mode,
always calls `enhance_environment()` before API consumers are constructed.

| Fixture/module | Loader | Role |
|---|---|---|
| `providers/sample/environment.py` | `PocRuntime` via `build_sample_environment()` | runtime-consumed base composition |
| `providers/sample/enhancement.py` | `PocRuntime` via `enhance_environment()` | runtime-consumed permanent SAMPLE enhancement |
| `providers/sample/medical_market.py` | `PocRuntime` SAMPLE market setup | runtime-consumed |
| `providers/sample/public_research.py` | `PocRuntime` SAMPLE market setup | runtime-consumed |
| `providers/sample/regional.py` | `environment.py` | runtime-consumed scenario data |
| `providers/sample/relationship_cases.py` | `environment.py` | runtime-consumed scenario data |
| `providers/sample/risk_cases.py` | `environment.py` | runtime-consumed scenario data |
| `providers/sample/rubric_examples.py` | `environment.py` | runtime-consumed scenario data |
| `providers/sample/scoring_cases.py` | `environment.py` | runtime-consumed scenario data |
| `providers/sample/pursuit_cases.py` | `environment.py` | runtime-consumed scenario data |
| `docs/research/enriched_commercial_sample.json` | `import_commercial_sample.py` only | import-only; not runtime-consumed |
| `docs/research/btx_researched_*.json`, `btx_research_integration_manifest.json`, `btx_sanitized_reference_data.json`, `btx_public_facility_feed_enrichment.json` | research ingestion and reference loaders called by `build_sample_environment()` | runtime-consumed SAMPLE identity/reference fixtures |
| `docs/research/btx_program_catalog.json`, `btx_component_taxonomy.json`, `btx_sample_*.json` | program, component, Paperless, Lake, CRM, and priority-scenario loaders called by `build_sample_environment()` | runtime-consumed SAMPLE catalog/commercial fixtures |

No runtime SAMPLE loader reads `docs/research/enriched_commercial_sample.json`;
the explicit operator import contract and validation use that file. Other
`docs/research/` JSON catalogs listed above are read at runtime through the
research loaders and `_catalog_support.document()`. The `providers/sample/`
boundary is the composition entry point, not the physical location of every
runtime-consumed fixture.
