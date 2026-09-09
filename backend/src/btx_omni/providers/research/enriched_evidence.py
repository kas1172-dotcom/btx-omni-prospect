"""Versioned public source metadata, not a substitute for live article retrieval."""
from functools import lru_cache

from btx_omni.providers.research._catalog_support import document


@lru_cache(maxsize=1)
def public_sources() -> dict[str, dict]:
    sources = document("enriched_public_sources.json")["sources"]
    indexed = {source["source_id"]: source for source in sources}
    if len(indexed) != len(sources):
        raise ValueError("Duplicate public source identity")
    return indexed
