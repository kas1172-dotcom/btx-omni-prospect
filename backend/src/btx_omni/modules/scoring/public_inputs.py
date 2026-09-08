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
