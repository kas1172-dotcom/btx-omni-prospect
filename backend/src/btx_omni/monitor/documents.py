"""Bounded feed-to-public-document enrichment inside the collection deadline."""
from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime

from btx_omni.ai.contracts import PublicEvidenceRecord
from btx_omni.monitor.contracts import SourceObservation
from btx_omni.providers.research.documents import extract_document
from btx_omni.providers.research.http import PublicFetchError, public_target


def enrich_feed_documents(observations: list[SourceObservation], *, fetch, cap: int) -> list[SourceObservation]:
    enriched = []
    for index, observation in enumerate(observations):
        payload = json.loads(observation.structured_payload or "{}")
        document = {"requested_url": observation.raw_evidence.locator,
                    "publication_date": observation.source_published_at.isoformat() if observation.source_published_at else None,
                    "publication_date_basis": "SOURCE_FEED", "event_date": None,
                    "retrieved_at": None, "extraction_status": "DOCUMENT_BUDGET_NOT_ATTEMPTED", "extraction_complete": False, "passages": []}
        if index < max(0, min(cap, 5)):
            try:
                host, _path, url = public_target(observation.raw_evidence.locator)
                status, body, headers = fetch(url, {"User-Agent": "OmniProspectMonitor/2.0", "Accept": "text/html,text/plain"})
                document["retrieved_at"] = datetime.now(UTC).isoformat()
                lowered = {key.lower(): value for key, value in headers.items()}
                final_host, _final_path, final_url = public_target(lowered.get("x-btx-resolved-url", url))
                document["publisher_host"] = final_host
                document["final_url"] = final_url
                document["publisher_redirected"] = final_host != host
                document["http_status"] = status
                if status != 200:
                    document["extraction_status"] = f"HTTP_{status}"
                else:
                    document.update(extract_document(body, lowered.get("content-type", "application/octet-stream")))
            except TimeoutError:
                raise  # never swallow the worker's outer collection deadline
            except (PublicFetchError, OSError, ValueError):
                document["extraction_status"] = "DOCUMENT_FETCH_FAILED"
        payload["_retrieved_document"] = document
        # Retrieval timestamps are audit metadata, not evidence changes. Identical
        # feed+document content must produce identical version/event identity.
        digest = observation.source_version.content_hash
        payload['_feed_content_hash'] = digest
        # Raw HTML checksums remain audit evidence, but changing analytics,
        # navigation or request nonces must not create a new public event.
        document["identity_basis"] = "FEED_FIELDS_AND_EXTRACTED_TEXT"
        if document.get("passages") and document.get("extracted_text_sha256"):
            digest = hashlib.sha256(f"{digest}:{document['extracted_text_sha256']}".encode()).hexdigest()
        version = replace(observation.source_version, content_hash=digest)
        source = observation.source_identity.source_system
        evidence = replace(observation.raw_evidence, id=f"evidence-{source}-{digest[:16]}", source_version=version)
        enriched.append(replace(observation, id=f"observation-{source}-{digest[:16]}", source_version=version, raw_evidence=evidence, structured_payload=json.dumps(payload, sort_keys=True, separators=(",", ":"))))
    return enriched


def retain_document_after_failed_refresh(observation: SourceObservation, previous_payload: str | None) -> SourceObservation:
    """Keep last successful passages only for the identical feed assertion.

    A failed attempt does not reverify the article. Retractions, successful empty
    responses and changed feed content must not inherit old supporting passages.
    """
    try:
        payload = json.loads(observation.structured_payload or '{}')
        previous = json.loads(previous_payload or '{}')
    except (TypeError, ValueError):
        return observation
    if not isinstance(payload, dict) or not isinstance(previous, dict):
        return observation
    attempt = payload.get('_retrieved_document', {})
    old = previous.get('_retrieved_document', {})
    if not isinstance(attempt, dict) or not isinstance(old, dict):
        return observation
    status = attempt.get('extraction_status', '')
    retryable = isinstance(status, str) and (status in {'DOCUMENT_FETCH_FAILED', 'DOCUMENT_BUDGET_NOT_ATTEMPTED', 'HTTP_403', 'HTTP_429'} or status.startswith('HTTP_5'))
    if not (retryable and payload.get('_feed_content_hash')
            and payload['_feed_content_hash'] == previous.get('_feed_content_hash')
            and attempt.get('requested_url') == old.get('requested_url')
            and old.get('passages') and old.get('extracted_text_sha256')):
        return observation
    retained = dict(old)
    retained['retained_after_unsuccessful_refresh'] = True
    retained['latest_refresh_attempt'] = attempt
    payload['_retrieved_document'] = retained
    digest = hashlib.sha256(f"{payload['_feed_content_hash']}:{old['extracted_text_sha256']}".encode()).hexdigest()
    version = replace(observation.source_version, content_hash=digest)
    source = observation.source_identity.source_system
    evidence = replace(observation.raw_evidence, id=f'evidence-{source}-{digest[:16]}', source_version=version)
    return replace(observation, id=f'observation-{source}-{digest[:16]}', source_version=version,
                   raw_evidence=evidence, structured_payload=json.dumps(payload, sort_keys=True, separators=(',', ':')))


def document_evidence(record: dict | None, *, max_passages: int = 8) -> tuple[PublicEvidenceRecord, ...]:
    """One shared persisted-source projection for Gemini consumers."""
    if not record:
        return ()
    cap = max(0, min(max_passages, 8))
    pools = [_single_document_evidence(record, max_passages=cap)]
    research = record.get('research') or {}
    result = research.get('result') or {}
    if (research.get('source_revision') == record.get('content_hash')
            and research.get('status') in {'COMPLETED', 'PAUSED'}
            and result.get('run_id') == research.get('run_id')):
        for source in result.get('documents', [])[:4]:
            pools.append(_single_document_evidence({
                'source_id': source['source_id'], 'source_url': source['url'], 'title': source['title'],
                'research_lineage': {'run_id': research['run_id'], 'source_revision': research['source_revision'],
                    'observation_id': record.get('observation_id'), 'status': research['status'],
                    'research_outcome': result.get('status')},
                'document': {**source['document'], 'retrieved_at': source.get('retrieved_at'),
                    'publication_date': source.get('publication_date'), 'final_url': source['url']},
            }, max_passages=cap))
    # Give each actually retrieved document a chance within the same caller
    # budget. Identical copied text does not become independent corroboration.
    selected, seen = [], set()
    for index in range(cap):
        for pool in pools:
            if index < len(pool) and pool[index].evidence_id not in seen:
                selected.append(pool[index])
                seen.add(pool[index].evidence_id)
                if len(selected) == cap:
                    return tuple(selected)
    return tuple(selected)


def _single_document_evidence(record: dict | None, *, max_passages: int) -> tuple[PublicEvidenceRecord, ...]:
    if not record or not record.get("document"):
        return ()
    document = record["document"]
    if document.get("extraction_status") not in {"TEXT_EXTRACTED", "TRUNCATED"}:
        return ()
    return tuple(PublicEvidenceRecord(
        passage["id"], (record.get("title") or "Retained public passage")[:500], passage["text"],
        document.get("final_url") or record["source_url"],
        json.dumps({"source_id": record["source_id"], "checksum_sha256": document.get("checksum_sha256"),
                    "retrieved_at": document.get("retrieved_at"), "publication_date": document.get("publication_date"),
                    "extraction_complete": document["extraction_complete"], "extraction_status": document["extraction_status"],
                    "retained_after_unsuccessful_refresh": document.get('retained_after_unsuccessful_refresh', False),
                    "latest_refresh_attempt": document.get('latest_refresh_attempt'),
                    "research_lineage": record.get('research_lineage'),
                    "selected_passages": min(max_passages, len(document.get("passages", []))),
                    "available_passages": len(document.get("passages", []))}, sort_keys=True),
    ) for passage in document.get("passages", [])[:max(0, min(max_passages, 8))])
