from __future__ import annotations

from btx_omni.core.classification import Classification
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.domain.relationships import AccountRelationshipEdge
from btx_omni.providers.research._catalog_support import document, source_provenance


def load_relationship_edges(*, account_ids: set[str], program_ids: set[str]) -> tuple[AccountRelationshipEdge, ...]:
    payload, result = document("btx_relationship_edges.json"), []
    source_ids = set(payload["sources"])
    semantic_edges: set[tuple[object, ...]] = set()
    for row in payload["edges"]:
        if row["from_account_id"] not in account_ids or row["to_account_id"] not in account_ids:
            raise ValueError(f"edge {row['edge_id']} has an unknown account")
        if row["from_account_id"] == row["to_account_id"]:
            raise ValueError(f"edge {row['edge_id']} cannot relate an account to itself")
        if not set(row.get("source_ids", ())) <= source_ids:
            raise ValueError(f"edge {row['edge_id']} has unknown source")
        program_id = row.get("program_id")
        if program_id is not None and program_id not in program_ids:
            raise ValueError(f"edge {row['edge_id']} has an unknown program")
        direction = row.get("direction", "bidirectional")
        endpoints: tuple[str, ...] = tuple(sorted((row["from_account_id"], row["to_account_id"]))) if direction == "bidirectional" else (row["from_account_id"], row["to_account_id"])
        semantic_key = (row["edge_type"], direction, program_id, *endpoints)
        if semantic_key in semantic_edges:
            raise ValueError(f"edge {row['edge_id']} duplicates an existing semantic relationship")
        semantic_edges.add(semantic_key)
        provenance = source_provenance(row, classification=Classification.PUBLIC, default_mode=DataMode.CONNECTED)
        result.append(AccountRelationshipEdge(row["edge_id"], row["from_account_id"], row["to_account_id"], row["edge_type"], direction, row["strength"], EvidenceState(row["evidence_state"]), tuple(row.get("source_ids", ())), row.get("narrative"), program_id, provenance))
    return tuple(result)
