"""Public Monitor evidence adapter for the existing deterministic score owner.

Registry source tiers and canonical resolution are server-owned inputs. Model
prose, publisher repetition and proposed commercial relevance cannot score them.
"""
from datetime import UTC
from decimal import Decimal
from hashlib import sha256

from btx_omni.modules.scoring.families import FactorInput, assess
from btx_omni.monitor.ontology import EventType, ResolutionState

VERSION = 'BTX_PUBLIC_SIGNAL_INPUTS_POC_1'
# Provisional source-quality bins; the family weights remain unchanged.
SOURCE_POINTS = {'TIER_1_AUTHORITATIVE_STRUCTURED': 100,
                 'TIER_2_AUTHORITATIVE_PUBLISHER': 90,
                 'TIER_3_REPUTABLE_SECONDARY': 70, 'TIER_4_DISCOVERY': 40}
RISK_INPUT_VERSION = 'BTX_PUBLIC_RISK_INPUTS_POC_1'
RISK_EVENT_TYPES = {
    EventType.CONTRACT_REDUCTION, EventType.PROGRAM_CANCELLATION,
    EventType.FACILITY_CLOSURE, EventType.WORKFORCE_REDUCTION,
    EventType.FINANCIAL_DISTRESS, EventType.EXPORT_RESTRICTION,
    EventType.PRODUCTION_DELAY,
}
LEVEL_POINTS = {'LOW': 25, 'MODERATE': 50, 'HIGH': 75, 'CRITICAL': 100}
PERSISTENCE_POINTS = {'TRANSIENT': 25, 'MONTHS': 50, 'ONE_YEAR': 75, 'STRUCTURAL': 100}
BREADTH_POINTS = {'RECORD': 25, 'FACILITY': 50, 'PROGRAM': 75, 'ENTERPRISE': 100}
REVERSIBILITY_POINTS = {'READY_MITIGATION': 25, 'MITIGATION_UNCERTAIN': 50, 'DIFFICULT': 75, 'IRREVERSIBLE': 100}


def public_signal_assessment(event, observation, *, now, freshness_hours):
    if now.tzinfo is None or freshness_hours <= 0:
        raise ValueError('Public assessments require an aware clock and freshness policy.')
    evidence = tuple(sorted({item.evidence_id for item in event.evidence}))
    bound = observation is not None and observation.raw_evidence.id in evidence
    source_evidence = (observation.raw_evidence.id,) if bound else ()
    published = observation.source_published_at if bound else event.source_published_at
    source_points = SOURCE_POINTS.get(observation.source_tier) if bound else None
    resolved = (event.resolution_state is ResolutionState.RESOLVED
                and bool(event.subject_entities)
                and all(item.state is ResolutionState.RESOLVED and item.canonical_account_id
                        for item in event.subject_entities))
    title = next((item for item in event.claims if item.predicate == 'source_title'
                  and item.value and set(item.evidence_ids) <= set(evidence)
                  and item.evidence_ids), None)
    required = ('typed_event', 'source_title', 'event_date', 'resolved_subject')
    observed = tuple(name for name, present in zip(required, (
        event.event_type is not EventType.UNCLASSIFIED_PUBLIC_UPDATE,
        title is not None, event.event_date is not None, resolved), strict=True) if present)
    # No publication date is substituted for the occurrence/effective date.
    age = (now - published).total_seconds() / 3600 if published else None
    freshness = (Decimal(100) if age <= freshness_hours else Decimal(0)) if age is not None and age >= 0 else None

    def factor(points, ids, reason, *, fields, present, raw=None):
        return FactorInput(Decimal(points) if points is not None and ids else None,
                           ids, reason, raw_value=raw, period=now.date().isoformat(),
                           truth_class='PUBLIC_SOURCE', required_fields=fields,
                           observed_fields=present)

    inputs = {
        'source_reliability': factor(source_points, source_evidence,
            'Source quality follows the registered publisher tier, not model language.',
            fields=('registered_source_tier',), present=('registered_source_tier',) if source_points is not None else (),
            raw=observation.source_tier if bound else None),
        'entity_match': factor(100 if resolved else None, evidence,
            'Canonical subject identity is resolved.' if resolved else 'Subject identity is unresolved; a proposed match is not evidence.',
            fields=('canonical_subject',), present=('canonical_subject',) if resolved else ()),
        'event_specificity': factor(Decimal(len(observed)) * 100 / len(required), evidence,
            'Specificity reflects the recorded event type, title, event date and subject; publication is not an event date.',
            fields=required, present=observed),
        'independent_corroboration': factor(None, (),
            'Independent source lineage has not been established. Copies and repeated collection do not prove corroboration.',
            fields=('independent_source_lineage',), present=()),
        'freshness': factor(freshness, source_evidence,
            f'Publication is evaluated against the source policy of {freshness_hours} hours. Unknown or future publication is not current.',
            fields=('publication_date',), present=('publication_date',) if freshness is not None else (),
            raw=published.isoformat() if published else None),
    }
    revision = sha256(repr((VERSION, event.id, event.event_type, event.event_date,
                           tuple(event.subject_entities), evidence,
                           tuple(sorted((c.predicate, c.value, tuple(sorted(set(c.evidence_ids)))) for c in event.claims)),
                           observation.source_version.content_hash if bound else None,
                           source_points, published, freshness_hours, freshness)).encode()).hexdigest()
    result = assess('signal_confidence', subject_id=event.id, as_of=now.astimezone(UTC).date().isoformat(),
                    revision=revision, inputs=inputs, eligible=bool(evidence) and not event.provenance.synthetic,
                    eligibility_reasons=('Public assertion assessment; independent of customer/prospect status and commercial priority.',))
    result['input_configuration_version'] = VERSION
    result['freshness_threshold_hours'] = freshness_hours
    result['band'] = ('HIGH' if result['score'] >= 70 else 'MEDIUM' if result['score'] >= 40 else 'LOW') if result['score'] is not None else 'INSUFFICIENT_EVIDENCE'
    return result


def public_risk_assessment(event, observation, *, now):
    """Map source-scoped risk assertions to the separate severity family.

    Only deterministic normalized claims may populate points. A model summary,
    headline sentiment, or a generic regulatory event cannot manufacture risk.
    """
    if now.tzinfo is None:
        raise ValueError('Public risk assessments require an aware clock.')
    evidence = {item.evidence_id for item in event.evidence}
    claims = {}
    for claim in event.claims:
        if claim.predicate not in claims and claim.evidence_ids and set(claim.evidence_ids) <= evidence:
            claims[claim.predicate] = claim
    explicit_negative = claims.get('risk_direction')
    eligible = event.event_type in RISK_EVENT_TYPES or bool(
        explicit_negative and explicit_negative.value.strip().upper() == 'NEGATIVE'
    )
    if not eligible:
        return None

    def categorical(predicate, mapping, label):
        claim = claims.get(predicate)
        key = claim.value.strip().upper() if claim else None
        points = mapping.get(key)
        ids = tuple(sorted(set(claim.evidence_ids))) if claim and points is not None else ()
        return FactorInput(
            Decimal(points) if points is not None else None, ids,
            f'{label}: {key.replace("_", " ").lower()}.' if points is not None else f'{label} is not established by a scoped source assertion.',
            raw_value=key, period=now.date().isoformat(), truth_class='PUBLIC_SOURCE',
            required_fields=(predicate,), observed_fields=(predicate,) if points is not None else (),
        )

    inputs = {
        'impact': categorical('risk_impact_level', LEVEL_POINTS, 'Potential BTX impact'),
        'materiality': categorical('risk_materiality_level', LEVEL_POINTS, 'Affected program, site, or business materiality'),
        'imminence': categorical('risk_imminence_level', LEVEL_POINTS, 'Timing imminence'),
        'persistence': categorical('risk_persistence', PERSISTENCE_POINTS, 'Expected persistence'),
        'breadth': categorical('risk_breadth', BREADTH_POINTS, 'Affected scope'),
        'reversibility': categorical('risk_reversibility', REVERSIBILITY_POINTS, 'Mitigation difficulty'),
    }
    revision = sha256(repr((RISK_INPUT_VERSION, event.id, event.event_type,
                           tuple(sorted((key, value.value, tuple(value.evidence_ids)) for key, value in claims.items())),
                           observation.source_version.content_hash if observation else None)).encode()).hexdigest()
    result = assess(
        'risk_severity', subject_id=event.id, as_of=now.astimezone(UTC).date().isoformat(),
        revision=revision, inputs=inputs, eligible=True,
        eligibility_reasons=('A negative public event is assessed independently from Signal Confidence and opportunity priority.',),
    )
    score = result['score']
    confidence = public_signal_assessment(event, observation, now=now, freshness_hours=24 * 30)['score']
    severity_band = 'HIGH' if score is not None and score >= 70 else 'MEDIUM' if score is not None and score >= 40 else 'LOW' if score is not None else 'INSUFFICIENT_EVIDENCE'
    confidence_band = 'HIGH' if confidence is not None and confidence >= 70 else 'MEDIUM' if confidence is not None and confidence >= 40 else 'LOW'
    disposition = ('INSUFFICIENT_EVIDENCE' if score is None else
                   'ESCALATE_NOW' if severity_band == 'HIGH' and confidence_band == 'HIGH' else
                   'VALIDATE_IMMEDIATELY' if severity_band == 'HIGH' else
                   'ACT_OR_MONITOR' if severity_band == 'MEDIUM' and confidence_band == 'HIGH' else
                   'RESEARCH_FURTHER' if severity_band == 'MEDIUM' else
                   'MONITOR' if confidence_band == 'HIGH' else 'FEED_ONLY')
    result.update({'input_configuration_version': RISK_INPUT_VERSION,
                   'band': severity_band, 'evidence_confidence_band': confidence_band,
                   'disposition': disposition})
    return result
