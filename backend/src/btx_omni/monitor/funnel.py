"""Immutable collection-stage diagnostics, not a claim of downstream publication."""
import json
from collections import Counter


def collection_funnel(observations, events, *, complete: bool, failures=()) -> dict:
    unique_events = {event.id: event for event in events}
    resolution = Counter(event.resolution_state.value for event in unique_events.values())
    relevance = Counter(event.seller_relevance_state.value for event in unique_events.values())
    extraction = Counter()
    refresh = Counter()
    document_checksums = []
    for observation in observations:
        document_checksums.append(None)
        try:
            payload = json.loads(observation.structured_payload or '{}')
        except (TypeError, ValueError):
            extraction['INVALID_STRUCTURED_PAYLOAD'] += 1
            continue
        if not isinstance(payload, dict):
            extraction['INVALID_STRUCTURED_PAYLOAD'] += 1
            continue
        document = payload.get('_retrieved_document')
        status = document.get('extraction_status', 'UNKNOWN') if isinstance(document, dict) else 'NO_DOCUMENT_EXTRACTION_RECORDED'
        extraction[status if isinstance(status, str) and len(status) <= 64 else 'INVALID_EXTRACTION_STATUS'] += 1
        if isinstance(document, dict):
            latest_attempt = document.get('latest_refresh_attempt') or document
            attempt_status = latest_attempt.get('extraction_status', 'UNKNOWN') if isinstance(latest_attempt, dict) else 'INVALID_EXTRACTION_STATUS'
            refresh[attempt_status if isinstance(attempt_status, str) and len(attempt_status) <= 64 else 'INVALID_EXTRACTION_STATUS'] += 1
            checksum = document.get('checksum_sha256')
            if isinstance(checksum, str) and len(checksum) == 64 and all(c in '0123456789abcdef' for c in checksum):
                document_checksums[-1] = checksum
    by_market = {}
    for market in sorted({market for event in unique_events.values() for market in event.markets}):
        selected = [event for event in unique_events.values() if market in event.markets]
        by_market[market] = {"normalized_events": len(selected), "resolved": sum(event.resolution_state.value == 'RESOLVED' for event in selected), "seller_eligible": sum(event.seller_relevance_state.value == 'RESOLVED_ELIGIBLE' for event in selected)}
    return {"version": "BTX_COLLECTION_FUNNEL_1", "stage": "COLLECTION_NORMALIZATION",
            "complete": complete, "upstream_retrieved_rows": None,
            "parseable_observations": len(observations),
            "distinct_source_records": len({(o.source_identity.source_system, o.source_identity.source_record_id) for o in observations}),
            "distinct_normalized_events": len(unique_events), "resolution_counts": dict(sorted(resolution.items())),
            "observation_lineage": [{"observation_id": o.id, "evidence_id": o.raw_evidence.id,
                                     "source_id": o.source_identity.source_system, "source_record_id": o.source_identity.source_record_id,
                                     "content_hash": o.source_version.content_hash, "observed_at": o.observed_at.isoformat(),
                                     "published_at": o.source_published_at.isoformat() if o.source_published_at else None,
                                     "document_checksum_sha256": checksum}
                                    for o, checksum in zip(observations, document_checksums, strict=True)],
            "seller_relevance_counts": dict(sorted(relevance.items())), "document_extraction_counts": dict(sorted(extraction.items())),
            "document_latest_attempt_counts": dict(sorted(refresh.items())),
            "by_market": by_market, "published_events": None, "actionable_outcomes": None,
            "failures": list(failures),
            "limits": ["Adapter raw retrieved/filtered row counts are not reported; parseable observations are not raw retrieval counts.",
                       "Market groups overlap; do not add them to obtain a total.",
                       "Seller eligibility is not publication, task creation, or external execution; downstream outcomes are not measured by this stage."]}
