from pathlib import Path

ROOT = Path(__file__).parents[1] / "src" / "btx_omni"
SURFACES = {
    "today": ROOT / "api" / "today.py",
    "map": ROOT / "api" / "map.py",
    "directory": ROOT / "api" / "accounts.py",
    "omni_retrieval": ROOT / "modules" / "assistant" / "commercial_tools.py",
    "briefings": ROOT / "api" / "intelligence.py",
    "gemini_prompts": ROOT / "ai" / "gemini.py",
}


def test_imported_network_storage_is_not_read_by_non_relationship_surfaces():
    forbidden = ("network_import", "network_people", "network_affiliations", "network_ties")
    for surface, path in SURFACES.items():
        assert path.exists(), surface
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), surface
