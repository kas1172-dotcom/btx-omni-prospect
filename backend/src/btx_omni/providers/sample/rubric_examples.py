"""Explicit what-if receipts: computed teaching cases, not customer allegations."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from btx_omni.core.clock import as_of_datetime, relative_date
from btx_omni.modules.scoring.commercial_decisions import customer_decisions
from btx_omni.modules.scoring.families import (
    FAMILIES,
    FactorInput,
    assess,
    overall_customer_risk,
)
from btx_omni.modules.scoring.public_inputs import public_signal_assessment
from btx_omni.monitor.contracts import EventEvidence, NormalizedClaim, SourceIdentity
from btx_omni.monitor.ontology import EventType
from btx_omni.providers.sample.enhancement import synthetic_record
from btx_omni.providers.sample.risk_cases import risk_context
from btx_omni.providers.sample.scoring_cases import customer


def corroboration_context(origins, *, anchor=None):
    event, observation = risk_context(anchor=anchor)
    evidence, claims, sources = list(event.evidence), list(event.claims), []
    for index, origin in enumerate(origins):
        eid = observation.raw_evidence.id if index == 0 else event.id + ':source:' + str(index)
        if index:
            evidence.append(EventEvidence(eid, ('independent_source_origin',), 'fictional_source_origin'))
        claims.append(NormalizedClaim('independent_source_origin', origin, (eid,), 'reviewed_independent_origin',
            'Fictional origin-lineage exercise; syndicated copies retain the same origin.'))
        sources.append(synthetic_record(evidence_id=eid, origin_id=origin, source_url='sample://fictional/' + eid,
            publisher='Fictional originating publisher ' + origin, event_date=relative_date(anchor=anchor), retrieval_date=relative_date(anchor=anchor)))
    return replace(event, claims=tuple(claims), evidence=tuple(evidence)), observation, sources


def examples(*, anchor=None):
    def scored(family, points, name):
        # Input bands are a transparent arithmetic exercise, not measured real KPIs.
        return assess(family, subject_id='fictional-what-if:' + name, as_of=relative_date(anchor=anchor), revision='sample-rubric-examples-1',
            eligible=True, inputs={key: FactorInput(Decimal(value), ('fictional-band-observation:' + name + ':' + key,),
                'Fictional band-table exercise; never attach this assumed band to a real customer.', raw_value=value)
                for (key, _), value in zip(FAMILIES[family].weights, points, strict=True)})
    internal = {name: scored('internal_commercial_risk', raw, name) for name, raw in
        [('low', [0, 0, 0, 0, 0, 0]), ('critical', [100, 100, 100, 100, 100, 0]), ('converged', [75] * 6)]}
    public = {name: scored('risk_severity', raw, name) for name, raw in
        [('low', [0, 0, 0, 0, 0, 0]), ('critical', [100, 100, 100, 100, 100, 0]), ('converged', [75] * 6)]}
    receipts = {}
    for name, ikey, pkey, link, block in [('public_floor', 'low', 'critical', (), ()),
        ('internal_floor', 'critical', 'low', (), ()), ('legal_floor', 'low', 'low', (), ('fictional-legal-prohibition',)),
        ('convergence', 'converged', 'converged', ('fictional-same-program-link',), ())]:
        receipts[name] = synthetic_record(internal=internal[ikey], public=public[pkey],
            overall=overall_customer_risk(current_customer=True, internal_score=internal[ikey]['score'], public_score=public[pkey]['score'],
                public_confirmed=True, convergence_evidence_ids=link, critical_override_evidence_ids=block),
            evidence=[synthetic_record(id=eid, confirmed=True, narrative='Authored what-if linking one fictional program disruption to its internal effects.' if link else
                'Authored what-if confirmed legal prohibition; execution remains blocked until explicit clearance.') for eid in (*link, *block)])
    gap = customer('watch', anchor=anchor)
    gap['relationship_profile'].pop('relationship_started_on')
    gap['relationship_profile']['risk_history_review_complete'] = False
    receipts['coverage_85'] = customer_decisions(gap, account_id=gap['account_id'], revision='example', current_customer=True)['customer_health']
    for age in (3, 9):
        event, observation = award_context(age, anchor=anchor)
        receipts[f'award_{age}_days'] = synthetic_record(label='Fictional SAM.gov-style modification, not a federal award',
            source_url=observation.raw_evidence.locator, publisher='Authored SAMPLE exercise',
            event_date=event.event_date.isoformat(), retrieval_date=relative_date(anchor=anchor),
            leaf_inputs={c.predicate: c.value for c in event.claims},
            assessment=public_signal_assessment(event, observation, now=as_of_datetime(anchor), freshness_hours=720))
    for name, origins in [('independent', ('publisher-a', 'publisher-b', 'publisher-c')), ('syndicated', ('publisher-a', 'publisher-a'))]:
        event, observation, sources = corroboration_context(origins, anchor=anchor)
        receipts[name] = synthetic_record(sources=sources, assessment=public_signal_assessment(event, observation, now=as_of_datetime(anchor), freshness_hours=720))
    return synthetic_record(label='Fictional rubric what-if lab — not current customer facts', examples=receipts)


def award_context(age_days, *, anchor=None):
    """SAM.gov-shaped single-source leaf data; no claim of an actual award."""
    event, observation = risk_context(anchor=anchor)
    published = as_of_datetime(anchor) - timedelta(seconds=float(Decimal(str(age_days)) * 86400))
    identifier = f'fictional-award-modification:{age_days}'
    eid = identifier + ':evidence'
    source = SourceIdentity('fictional_rubric_fixture', identifier)
    version = replace(observation.source_version, source_record_id=identifier)
    raw = replace(observation.raw_evidence, id=eid, source_identity=source, source_version=version,
                  locator='sample://fictional/' + identifier, excerpt='Fictional award modification obligates additional funding for a demonstration machining work package.')
    observation = replace(observation, id=identifier + ':observation', source_identity=source, source_version=version,
        source_published_at=published, raw_evidence=raw, title='Fictional SAM.gov-style modification', structured_payload=None)
    values = {'fictional_scenario': 'true', 'recipient': 'Fictional Risk Manufacturing',
        'instrument_id': 'SAMPLE-NOT-A-FEDERAL-AWARD', 'action_type': 'MODIFICATION', 'amount': '1000000',
        'amount_basis': 'synthetic additional obligation, not total ceiling', 'effective_date': published.date().isoformat(),
        'work_description': 'Fictional precision-machining demonstration work package',
        'site_identity_verified': 'true', 'authoritative_identifier_verified': 'true'}
    return replace(event, id=identifier, event_type=EventType.CONTRACT_MODIFICATION,
        event_date=published, source_published_at=published,
        claims=tuple(NormalizedClaim(k, v, (eid,), 'reviewed_internal_record', 'Fictional band-table source') for k, v in values.items()),
        evidence=(EventEvidence(eid, tuple(values), 'fictional_single_primary_record'),),
        provenance=replace(event.provenance, source_record_id=identifier, source_url=raw.locator)), observation
