"""Explicitly fictional filing exercises, never allegations about real companies."""
import json
from dataclasses import replace
from hashlib import sha256

from btx_omni.core.clock import as_of_datetime, relative_date
from btx_omni.monitor.contracts import (
    EntityResolution,
    EventEvidence,
    NormalizedClaim,
    SourceIdentity,
    SourceVersion,
)
from btx_omni.monitor.ontology import EventType, ResolutionState, SellerRelevanceState
from btx_omni.providers.sample.kratos import context


def risk_context(*, confidence='HIGH', anchor=None):
    event, observation = context()
    aid = 'demo-fictional-risk' if confidence == 'HIGH' else 'demo-fictional-at-risk'
    identity = aid + ':filing:' + confidence.lower()
    eid = identity + ':evidence'
    now = as_of_datetime(anchor)
    source = SourceIdentity('fictional_rubric_fixture', identity)
    version = SourceVersion(identity, '1', sha256(identity.encode()).hexdigest(), now, now)
    reference = replace(observation.raw_evidence, id=eid, source_identity=source, source_version=version,
                        locator='sample://fictional/' + identity, captured_at=now,
                        excerpt='Fictional facility consolidation across two business units. A plan exists but has not started; there is no allegation about any real company.')
    observation = replace(observation, id=identity + ':observation', source_identity=source, source_version=version,
        observed_at=now, raw_evidence=reference, source_published_at=now,
        source_tier='TIER_1_AUTHORITATIVE_STRUCTURED' if confidence == 'HIGH' else 'TIER_4_DISCOVERY',
        structured_payload=None, title=('Fictional consolidation exercise — not a public filing' if confidence == 'HIGH' else
            'UNCONFIRMED fictional consolidation hypothesis — validate immediately; not a real allegation'))
    facts = {'fictional_scenario': 'true', 'source_title': observation.title,
        'legal_entity': 'Fictional Risk Manufacturing', 'record_id': identity, 'event_type': 'consolidation',
        'report_date': relative_date(anchor=anchor), 'affected_scope': 'two fictional business units',
        'site_identity_verified': 'true', 'authoritative_identifier_verified': 'true',
        'risk_condition': 'FACILITY_CLOSURE', 'affected_revenue_share_percent': '30', 'affected_backlog_share_percent': '25',
        'days_until_effect': '0', 'remaining_effect_days': '400', 'risk_breadth': 'MULTIPLE_BUSINESS_UNITS',
        'risk_mitigation': 'PLAN_NOT_STARTED'}
    if confidence != 'HIGH':
        for key in ('legal_entity', 'record_id', 'event_type', 'report_date', 'site_identity_verified', 'authoritative_identifier_verified'):
            facts.pop(key, None)
    seed = {'seed_type': 'curated_monitor_style', 'fictional_scenario': True, 'synthetic': True, 'data_mode': 'SAMPLE',
            'source_url': reference.locator, 'publisher': 'Authored fictional filing exercise',
            'event_date': relative_date(anchor=anchor), 'retrieval_date': relative_date(anchor=anchor),
            'affected_scope': 'Two fictional business units; applicability to an actual company is expressly denied.',
            'mitigation_notes': 'An unstarted consolidation plan is assumed in this exercise. Validate milestones and customer coverage.',
            'open_applicability_questions': ['Is the scenario evidence corroborated?', 'Which precise site and work package are affected?'],
            'contacts': 'Sourcing and remediation role gaps; no named people.', 'routes': [],
            'entity': {'site': 'Fictional demonstration site', 'site_status': 'FICTIONAL_SAMPLE'},
            'gates': {'need': 'UNKNOWN', 'publication': 'FICTIONAL_SAMPLE_NOT_A_PUBLIC_ALLEGATION'},
            'contact_gap': {'role': 'risk remediation owner', 'state': 'NO_NAMED_PERSON_RESEARCHED'},
            'fit_hypothesis': {'label': 'Fit hypothesis', 'reasoning': 'No supply or sourcing need follows from this risk exercise.'},
            'what_would_change_result': ['Verify entity, source record and affected scope before treating an allegation as confirmed.',
                                       'A completed mitigation milestone changes severity, not source reliability.'],
            'label': observation.title}
    observation = replace(observation, structured_payload=json.dumps(seed, sort_keys=True))
    claims = tuple(NormalizedClaim(k, v, (eid,), 'reviewed_internal_record', 'fictional rubric exercise') for k, v in facts.items())
    return replace(event, id=identity, event_type=EventType.FINANCIAL_DISTRESS,
        subject_entities=(EntityResolution('Fictional Risk Manufacturing', aid, ResolutionState.RESOLVED,
                                           'sample entity ID', 'fictional scenario only'),),
        program=replace(event.program, mention='Fictional platform'), geography='Fictional demonstration site',
        event_date=now, source_published_at=now, claims=claims, evidence=(EventEvidence(eid, tuple(facts), 'fictional_source_record'),),
        provenance=replace(event.provenance, source_system='fictional_rubric_fixture', source_record_id=identity,
                           source_url=reference.locator, observed_at=now, recorded_at=now, synthetic=True, missing_fields=()),
        resolution_state=ResolutionState.RESOLVED, seller_relevance_state=SellerRelevanceState.RESOLVED_ELIGIBLE), observation
