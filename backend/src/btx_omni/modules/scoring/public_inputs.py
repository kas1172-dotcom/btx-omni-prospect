"""Public Monitor evidence adapter for the existing deterministic score owner.

Registry source tiers and canonical resolution are server-owned inputs. Model
prose, publisher repetition and proposed commercial relevance cannot score them.
"""
import json
from dataclasses import asdict
from datetime import UTC
from decimal import Decimal
from hashlib import sha256

from btx_omni.core.clock import evidence_state
from btx_omni.modules.scoring.families import FactorInput, assess
from btx_omni.modules.scoring.public_rules import (
    GOVERNMENT_SOURCES,
    RISK_FIELDS,
    SOURCE_POINTS,
    freshness_points,
    freshness_window_hours,
    required_fields,
    risk_points,
)
from btx_omni.monitor.ontology import EventType, ResolutionState

VERSION = 'BTX_PUBLIC_SIGNAL_INPUTS_V2'
RISK_INPUT_VERSION = 'BTX_PUBLIC_RISK_INPUTS_V2'
RISK_EVENT_TYPES = {
    EventType.CONTRACT_REDUCTION, EventType.PROGRAM_CANCELLATION,
    EventType.FACILITY_CLOSURE, EventType.WORKFORCE_REDUCTION,
    EventType.FINANCIAL_DISTRESS, EventType.EXPORT_RESTRICTION, EventType.PRODUCTION_DELAY,
}


def _claims(event):
    evidence = {item.evidence_id for item in event.evidence}
    candidates = {}
    for claim in event.claims:
        if claim.evidence_ids and set(claim.evidence_ids) <= evidence and claim.extraction_method in {
            'deterministic_structured_mapping', 'reviewed_source_extraction', 'reviewed_internal_record'
        }:
            candidates.setdefault(claim.predicate, []).append(claim)
    # Conflicting equal-authority assertions remain unknown, never first-wins.
    return {key: values[0] for key, values in candidates.items() if len({v.value for v in values}) == 1}


def public_signal_assessment(event, observation, *, now, freshness_hours):
    if now.tzinfo is None or freshness_hours <= 0:
        raise ValueError('Public assessments require an aware clock and freshness policy.')
    evidence = tuple(sorted({item.evidence_id for item in event.evidence}))
    bound = observation is not None and observation.raw_evidence.id in evidence
    source_evidence = (observation.raw_evidence.id,) if bound else ()
    claims = _claims(event)
    facts = {key: item.value for key, item in claims.items()}
    published = observation.source_published_at if bound else event.source_published_at
    tier = observation.source_tier if bound else None
    source_points = (100 if observation.source_identity.source_system in GOVERNMENT_SOURCES else SOURCE_POINTS.get(tier)) if bound else None
    resolved = (event.resolution_state is ResolutionState.RESOLVED and bool(event.subject_entities)
                and all(item.state is ResolutionState.RESOLVED and item.canonical_account_id for item in event.subject_entities))
    # Parent identity is not subsidiary/site resolution.
    entity_points = 50 if resolved else 0
    if facts.get('identity_resolution_scope') == 'PARENT_CONFIRMED_SITE_UNRESOLVED':
        entity_points = 50
    if resolved and facts.get('site_identity_verified') == 'true':
        if facts.get('authoritative_identifier_verified') == 'true':
            entity_points = 100
        elif facts.get('legal_name_address_verified') == 'true':
            entity_points = 75
    required = required_fields(event.event_type.value)
    observed = tuple(name for name in required if facts.get(name))
    age = (now - published).total_seconds() / 3600 if published else None
    window = freshness_window_hours(event.event_type.value)
    freshness = freshness_points(age, window)
    origins = {claim.value for claim in event.claims if claim.predicate == 'independent_source_origin'
               and claim.extraction_method == 'reviewed_independent_origin' and claim.evidence_ids
               and set(claim.evidence_ids) <= set(evidence)}
    # Without an independently reviewed origin map, the bound primary source is
    # exactly one origin. Copies and model assertions never increase this count.
    count = len(origins) if origins else 1 if bound else 0

    def factor(points, ids, reason, raw=None):
        return FactorInput(Decimal(points) if points is not None and ids else None, ids, reason,
                           raw_value=raw, period=now.date().isoformat(), truth_class='POC_SCENARIO' if event.provenance.synthetic else 'PUBLIC_SOURCE')

    inputs = {
        'source_reliability': factor(source_points, source_evidence, 'Reliability follows the authenticated source category, not commercial relevance.', tier),
        'entity_match': factor(entity_points, evidence, 'Identity matching distinguishes a resolved parent from a verified site or subsidiary.', entity_points),
        'event_specificity': factor(Decimal(len(observed)) * 100 / len(required) if bound else None, source_evidence,
            'Specificity measures the required fields for this event type; missing fields reduce the contribution.', f'{len(observed)}/{len(required)}'),
        'independent_corroboration': factor(100 if count >= 3 else 75 if count == 2 else 25 if count == 1 else 0,
            source_evidence or evidence, 'Independently originated sources, not copied articles or repeated collections.', count),
        'freshness': factor(freshness, source_evidence,
            f'Fact freshness uses the rubric’s {window // 24}-day window; collection time does not reset publication age.', published.isoformat() if published else None),
    }
    # R1/R2: retain the explicit section-4 zero freshness band, but do not
    # present expired source observations as a current High confidence score.
    if age is not None and age > window:
        from dataclasses import replace
        inputs = {key: replace(value, evidence_state='STALE') if key != 'freshness' else value
                  for key, value in inputs.items()}
    # Persistence may reorder payload keys. Hash scoring inputs canonically,
    # not repr(event/observation), so worker and API reads share one identity.
    revision = sha256(json.dumps({'version': VERSION, 'event': event.id,
        'source_revision': observation.source_version if observation else None,
        'window': window, 'as_of': now.astimezone(UTC).date().isoformat(),
        'inputs': {key: asdict(value) for key, value in inputs.items()}},
        sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()
    result = assess('signal_confidence', subject_id=event.id, as_of=now.astimezone(UTC).date().isoformat(),
                    revision=revision, inputs=inputs, eligible=bool(evidence) and (not event.provenance.synthetic or
                        (event.provenance.source_system == 'fictional_rubric_fixture' and event.provenance.data_mode.value == 'SAMPLE' and facts.get('fictional_scenario') == 'true')))
    result.update({'input_configuration_version': VERSION, 'freshness_threshold_hours': window,
                   'evidence_state': 'STALE' if age is not None and age > window else 'CURRENT' if freshness is not None else 'UNKNOWN',
                   'collection_freshness_hours': freshness_hours, 'specificity_required_fields': required,
                   'specificity_missing_fields': tuple(name for name in required if name not in observed),
                   'seller_recommendation_eligible': bool(not event.provenance.synthetic and source_points is not None and source_points >= 50 and entity_points >= 75 and count and freshness not in {None, 0}),
                   'synthetic': event.provenance.synthetic, 'data_mode': event.provenance.data_mode.value})
    result['band'] = ('HIGH' if result['score'] >= 70 else 'MEDIUM' if result['score'] >= 40 else 'LOW') if result['score'] is not None else 'INSUFFICIENT_EVIDENCE'
    return result


def public_risk_assessment(event, observation, *, now):
    if now.tzinfo is None:
        raise ValueError('Public risk assessments require an aware clock.')
    claims = _claims(event)
    facts = {key: item.value for key, item in claims.items()}
    if event.event_type not in RISK_EVENT_TYPES and facts.get('risk_direction') != 'NEGATIVE':
        return None
    inputs = {}
    published = observation.source_published_at if observation else event.source_published_at
    state = evidence_state(published, as_of=now, window_days=freshness_window_hours(event.event_type.value) // 24)
    for key, fields in RISK_FIELDS.items():
        points = risk_points(key, facts)
        ids = tuple(sorted({eid for field in fields if field in claims for eid in claims[field].evidence_ids}))
        inputs[key] = FactorInput(Decimal(points) if points is not None and ids else None, ids,
            f'{key.capitalize()}: source-scoped observations follow rubric v2; evidence is {state}.' if points is not None
            else f'{key.capitalize()}: quantified, scoped evidence is missing.',
            raw_value=str({key: facts[key] for key in fields if key in facts}), period=now.date().isoformat(), truth_class='POC_SCENARIO' if event.provenance.synthetic else 'PUBLIC_SOURCE', evidence_state=state)
    revision = sha256(repr((RISK_INPUT_VERSION, event.id, sorted(facts.items()), observation.source_version if observation else None)).encode()).hexdigest()
    result = assess('risk_severity', subject_id=event.id, as_of=now.astimezone(UTC).date().isoformat(),
                    revision=revision, inputs=inputs, eligible=True)
    score = result['score']
    confidence = public_signal_assessment(event, observation, now=now, freshness_hours=24 * 30)['score']
    severity_band = 'CRITICAL' if score is not None and score >= 85 else 'HIGH' if score is not None and score >= 70 else 'MODERATE' if score is not None and score >= 40 else 'LOW' if score is not None else 'INSUFFICIENT_EVIDENCE'
    confirmed = confidence is not None and confidence >= 70
    disposition = ('INSUFFICIENT_EVIDENCE' if score is None else 'ESCALATE_NOW' if score >= 70 and confirmed
                   else 'VALIDATE_IMMEDIATELY' if score >= 70 else 'ACT_OR_MONITOR' if score >= 40 and confirmed
                   else 'RESEARCH_FURTHER' if score >= 40 else 'MONITOR' if confirmed else 'FEED_ONLY')
    result.update({'input_configuration_version': RISK_INPUT_VERSION, 'band': severity_band,
                   'evidence_state': state,
                   'synthetic': event.provenance.synthetic, 'data_mode': event.provenance.data_mode.value,
                   'evidence_confidence_band': 'HIGH' if confirmed else 'MEDIUM' if confidence is not None and confidence >= 40 else 'LOW',
                   'disposition': disposition})
    return result
