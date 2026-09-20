"""Curated public-source research seed, never a live monitor receipt."""
import json
from hashlib import sha256

from btx_omni.core.clock import as_of_datetime
from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.contracts import (
    EventEvidence, IntelligenceEvent, NormalizedClaim, ProgramResolution,
    RawEvidenceReference, SourceIdentity, SourceObservation, SourceVersion,
)
from btx_omni.monitor.ontology import EventType, ResolutionState

PRIMARY = 'https://ir.kratosdefense.com/news-releases/news-release-details/kratos-providing-spartan-j85-engines-support-boeing-jdam-lr'
MIRROR = 'https://www.kratosdefense.com/newsroom/kratos-providing-spartan-j85-engines-to-support-boeing-jdam-lr-production-contract'
IDENTITY = 'kratos-tdi-jdam-lr-2026-08'


def payload():
    return {
        'signal_id': IDENTITY, 'seed_type': 'curated_monitor_style', 'data_mode': 'SAMPLE',
        'retrieval_date': '2026-09-20', 'publisher': 'Kratos Defense & Security Solutions',
        'event_date': '2026-08-24', 'source_url': PRIMARY, 'retrieved_primary_mirror_url': MIRROR,
        'retrieval_note': 'Investor URL returned HTTP 403; same dated company release verified on the corporate newsroom.',
        'entity': {'legal_name': 'Kratos Defense & Security Solutions, Inc.',
                   'business_unit': 'Technical Directions, Inc. (TDI)', 'site': 'Auburn Hills, Michigan',
                   'site_scope': 'J85 engine production', 'street_address': None, 'latitude': None, 'longitude': None,
                   'cage_uei': None, 'site_status': 'city_resolved_exact_site_needs_verification'},
        'assertion': 'Kratos allocated expanded Spartan capacity to Boeing JDAM-LR. The release identifies Auburn Hills as the J85 engine production location.',
        'history': [
            {'role': 'trade_press_on_boeing_award', 'event_date': '2026-08-05', 'retrieval_date': '2026-09-20',
             'publisher': 'Air & Space Forces Magazine', 'source_url': 'https://www.airandspaceforces.com/long-range-jdam-air-force-new-standoff-strike-option/',
             'assertion': 'User-provided historical report of a $75M USAF production award to Boeing.', 'window_days': 7, 'state': 'STALE', 'verification': 'USER_SUPPLIED_HISTORY'},
            {'role': 'entity_reference', 'event_date': '2024-09-12', 'retrieval_date': '2026-09-20',
             'publisher': 'Kratos via GlobeNewswire', 'source_url': 'https://finance.yahoo.com/news/kratos-announces-immediate-availability-tdi-120000356.html',
             'assertion': 'User-provided historical TDI location: Oxford, Michigan.', 'window_days': 180,
             'state': 'STALE', 'superseded_by': IDENTITY, 'verification': 'USER_SUPPLIED_HISTORY'},
        ],
        'gates': {'identity': 'PARTIAL', 'need': 'UNKNOWN', 'qualified': 'UNKNOWN', 'publication': 'RESEARCH_ONLY'},
        'contact_gap': {'role': 'sourcing', 'name': None, 'email': None, 'state': 'NOT_RESEARCHED'},
        'fit_hypothesis': {'label': 'fit hypothesis', 'reasoning': 'Engine production suggests a component-manufacturing research question, but no sourced BTX component scope, external sourcing need or likely order is established.'},
        'routes': [
            {'from': 'Boeing', 'to': 'JDAM-LR', 'state': 'COMPANY_STATEMENT', 'source_url': MIRROR},
            {'from': 'JDAM-LR', 'to': 'Kratos TDI', 'state': 'COMPANY_STATEMENT', 'source_url': MIRROR},
            {'from': 'BTX', 'to': 'Boeing JDAM-LR', 'state': 'UNSUPPORTED_HYPOTHESIS', 'source_url': None,
             'reason': 'Synthetic BTX commercial history does not establish supply into this public program.'},
        ],
        'do_not_attach': ['Kratos $35M August 31 hardware award: program and unit unspecified.'],
        'what_would_change_result': ['Verify the legal entity identifier and exact production-site address.',
                                      'Obtain dated evidence of a relevant external sourcing requirement.',
                                      'Identify the sourcing role without inventing a person or introduction.'],
    }


def context():
    data = payload()
    retrieved = as_of_datetime(data['retrieval_date'])
    published = as_of_datetime(data['event_date'])
    encoded = json.dumps(data, sort_keys=True)
    identity = SourceIdentity('curated_monitor_style', IDENTITY)
    version = SourceVersion(IDENTITY, '1', sha256(encoded.encode()).hexdigest(), retrieved, retrieved)
    eid = IDENTITY + ':primary'
    evidence = RawEvidenceReference(eid, identity, version, PRIMARY, retrieved, data['assertion'], 'text/html')
    observation = SourceObservation(IDENTITY + ':observation', identity, version, retrieved,
        'Kratos TDI J85 production — curated research lead', evidence, published,
        source_tier='TIER_2_AUTHORITATIVE_PUBLISHER', structured_payload=encoded)
    facts = {'source_title': data['assertion'], 'organization': data['entity']['legal_name'],
             'site': 'Auburn Hills, Michigan', 'change_type': 'Spartan capacity allocation',
             'effective_date': data['event_date'], 'affected_operation': 'J85 engine production',
             'identity_resolution_scope': 'PARENT_CONFIRMED_SITE_UNRESOLVED',
             'seed_type': data['seed_type']}
    claims = tuple(NormalizedClaim(k, v, (eid,), 'reviewed_source_extraction', 'company release; not independently corroborated') for k, v in facts.items())
    provenance = Provenance('curated_monitor_style', IDENTITY, PRIMARY, retrieved, retrieved,
        Classification.PUBLIC, EvidenceState.CONFIRMED, DataMode.SAMPLE, False,
        missing_fields=('Sourcing contact role', 'External sourcing need', 'Exact site address and coordinates', 'Authoritative CAGE/UEI'))
    event = IntelligenceEvent(IDENTITY, EventType.CAPACITY_EXPANSION, (), (),
        ProgramResolution('JDAM-LR', None, ResolutionState.UNRESOLVED, 'company statement', 'not canonical program publication'),
        'Auburn Hills, Michigan', published, None, None, claims,
        (EventEvidence(eid, tuple(facts), 'primary_company_statement'),), provenance,
        'Direct company statement', 'Reviewed paraphrase', 'Parent known; authoritative identifier and exact site unresolved',
        'One origin; company mirrors are not corroboration', ResolutionState.UNRESOLVED,
        markets=('Defense',), source_published_at=published)
    return event, observation
