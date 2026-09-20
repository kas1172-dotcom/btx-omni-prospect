"""J1/J3 fictional Southwest cohort. Coordinates are demonstration pins, not sites."""
import json
from dataclasses import replace
from decimal import Decimal

from btx_omni.core.classification import Classification
from btx_omni.core.clock import as_of_datetime, relative_date
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
    AccountFacility,
    AccountRelationship,
    CanonicalAccount,
    ResearchProvenance,
)
from btx_omni.domain.btx import BtxFacility
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.providers.sample.enhancement import (
    VERSION,
    empty_ledger,
    reconcile_months,
    synthetic_record,
)
from btx_omni.providers.sample.scoring_cases import customer

COHORT = (
    ('aero', 'Commercial Aerospace', 'PROSPECT', '336413'),
    ('defense', 'Defense', 'CURRENT_CUSTOMER', '336419'),
    ('space', 'Space', 'FORMER_CUSTOMER', '336414'),
    ('semi', 'Semiconductor', 'PROSPECT', '333242'),
    ('medical-customer', 'Medical', 'CURRENT_CUSTOMER', '339112'),
    ('robotics', 'Robotics', 'PROSPECT', '333998'),
    ('medical-partner', 'Medical', 'PROSPECT', '339113'),
    ('medical-prospect', 'Medical', 'PROSPECT', '339114'),
    ('aero-partner', 'Commercial Aerospace', 'PROSPECT', '336413'),
)
IDS = tuple('demo-regional-' + row[0] for row in COHORT)


def prospect_evidence(aid, *, low=False, anchor=None):
    # Exact 80 without a fabricated named contact: 30+18.75+15+11.25+5+0.
    states = {'target_cohort_match': 'EXPLORATORY' if low else 'PRIMARY',
        'manufacturing_fit': 'COMPONENT_ADJACENCY' if low else 'ONE_MATCHING_SITE',
        'outsourcing_posture': 'HISTORICAL' if low else 'EXTERNAL_SUPPLIERS',
        'strategic_archetype': 'INTERMEDIARY' if low else 'COMPONENT_MANUFACTURER', 'existing_btx_access': 'RESEARCHED_NO_ACCESS'}
    rows = {key: {'state': value} for key, value in states.items()}
    rows['scale'] = {'organization_ttm_revenue_usd': 1_000_000 if low else 1_000_000_000}
    return {key: synthetic_record(**raw, account_id=aid, evidence_ids=[aid + ':profile'],
        source_urls=['sample://fictional/' + aid], review_state='VERIFIED', reviewed_as_of=relative_date(anchor=anchor),
        reason='Authored fictional private-company profile. Not public financials or real buyer access.') for key, raw in rows.items()}


def regional_environment(base, *, anchor=None):
    accounts, facilities, ledgers = [], [], {}
    now = as_of_datetime(anchor)
    for index, (slug, market, status, naics) in enumerate(COHORT):
        aid = 'demo-regional-' + slug
        name = 'Fictional Southwest ' + slug.replace('-', ' ').title() + ' — SAMPLE'
        source = 'sample://fictional/' + aid
        prov = Provenance(VERSION, aid, source, now, now, Classification.INTERNAL_COMMERCIAL, EvidenceState.CONFIRMED, DataMode.SAMPLE, True)
        research = ResearchProvenance((aid + ':profile',), (source,), 'FICTIONAL_SAMPLE', now, True)
        accounts.append(CanonicalAccount(aid, name, AccountRelationship(status), aid + '.example', (market,),
            contact_role_families=('procurement', 'engineering'), provenance=prov, public_research_state='FICTIONAL_SAMPLE',
            prospect_rationale='Fictional demonstration profile; sourcing contact is a visible gap, not a named person.',
            secondary_classifications=('Medical Device',) if market == 'Medical' else (),
            btx_top_100=slug == 'aero-partner', btx_top_100_provenance=research if slug == 'aero-partner' else None,
            prospect_fit_evidence=prospect_evidence(aid, low=slug == 'medical-prospect', anchor=anchor)))
        facilities.append(AccountFacility(aid + ':site', aid, name + ' operating site', 'Fictional Phoenix-area pin', 'AZ',
            Decimal('33.45') + Decimal(index) / 100, Decimal('-112.07') + Decimal(index) / 80,
            facility_type='HEADQUARTERS' if slug == 'robotics' else 'OPERATING_SITE', verification_state='FICTIONAL_SAMPLE_LOCATION',
            source_url=source, source_type='AUTHORED_SAMPLE', last_verified_at=now, provenance=research))
        if status == 'CURRENT_CUSTOMER':
            ledger = json.loads(json.dumps(customer('healthy', anchor=anchor)).replace('demo-fictional-healthy', aid))
            ledger['identity']['display_name'] = name
        else:
            ledger = empty_ledger(aid, name, anchor=anchor)
            ledger['programs'].append(synthetic_record(program_id=aid + ':program', name='Fictional ' + market + ' platform',
                description='Demonstration component requirements only; not a claim of a public program or awarded work.'))
            ledger['components'].append(synthetic_record(component_id=aid + ':component', program_id=aid + ':program',
                name='Fictional precision housing', business_unit_id='BU-ERA', technical_requirements={'process': 'CNC machining'}))
            reconcile_months(ledger)
        ledger['naics_assignments'] = [synthetic_record(code=naics, taxonomy_version='NAICS2022', assignment_basis='FICTIONAL_SCENARIO')]
        ledger['site_context'] = synthetic_record(website='https://' + aid + '.example', site_id=aid + ':site',
            location_basis='FICTIONAL_DEMO_PIN_NOT_A_VERIFIED_REAL_ADDRESS', headquarters=slug == 'robotics',
            market=market, medical_device=market == 'Medical', naics=naics,
            programs=[r['name'] for r in ledger['programs']],
            component_fit='Fit hypothesis: housing geometry may suit CNC work; qualification and tolerances remain to be confirmed.',
            capability_constraints=['No site qualification or reserved capacity is asserted.'],
            strategic_partnership=slug.endswith('partner'), top_100_membership='FICTIONAL_SAMPLE_ONLY' if slug == 'aero-partner' else None,
            contact_gap='Sourcing role not researched. No named person, email, meeting or introduction is available.',
            source_url=source, publisher='BTX authored fictional demo', event_date=relative_date(anchor=anchor), retrieval_date=relative_date(anchor=anchor))
        ledgers[aid] = ledger
    btx = BtxFacility('demo-btx-southwest', 'era-industries', 'Fictional BTX Southwest demonstration site — SAMPLE',
        'Fictional Phoenix-area pin', 'AZ', 'US', Decimal('33.46'), Decimal('-112.06'), 'FICTIONAL_SAMPLE_LOCATION',
        'sample://fictional/btx-southwest', 'AUTHORED_SAMPLE',
        Provenance(VERSION, 'demo-btx-southwest', 'sample://fictional/btx-southwest', now, now,
                   Classification.INTERNAL_COMMERCIAL, EvidenceState.CONFIRMED, DataMode.SAMPLE, True))
    origin = AccountFacility('demo-watch-southwest', 'demo-fictional-watch', 'Fictional Watch Manufacturing Southwest site — SAMPLE',
        'Fictional Phoenix-area pin', 'AZ', Decimal('33.44'), Decimal('-112.08'), facility_type='OPERATING_SITE',
        verification_state='FICTIONAL_SAMPLE_LOCATION', source_url='sample://fictional/demo-watch-southwest',
        source_type='AUTHORED_SAMPLE', last_verified_at=now,
        provenance=ResearchProvenance(('demo-watch-southwest',), ('sample://fictional/demo-watch-southwest',), 'FICTIONAL_SAMPLE', now, True))
    facilities.append(origin)
    return replace(base, accounts=base.accounts + tuple(accounts), facilities=base.facilities + tuple(facilities),
                   public_facilities=base.public_facilities + tuple(facilities), btx_facilities=base.btx_facilities + (btx,)), ledgers
