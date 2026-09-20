"""J5 joins a verified public development to separately synthetic account context."""
from dataclasses import replace

from btx_omni.monitor.contracts import EntityResolution
from btx_omni.monitor.ontology import ResolutionState, SellerRelevanceState
from btx_omni.providers.sample.enhancement import synthetic_record
from btx_omni.providers.sample.kratos import MIRROR, context, payload


def expansion_context():
    event, observation = context()
    # The company release explicitly names Boeing's program, not a BTX supply edge.
    event = replace(event, id='demo-j5-boeing-public-context',
        subject_entities=(EntityResolution('Boeing', 'boeing', ResolutionState.RESOLVED,
                                           'named in primary company statement', 'Parent program context only; no Boeing site attribution.'),),
        resolution_state=ResolutionState.RESOLVED, seller_relevance_state=SellerRelevanceState.RESOLVED_NEEDS_REVIEW)
    return event, replace(observation, title='Kratos capacity allocation supports Boeing JDAM-LR — public context, not BTX supply evidence')


def add_boeing_expansion(account):
    public = payload()
    rid = lambda key: 'demo:j5:boeing:' + key
    account['components'].append(synthetic_record(component_id=rid('component'), program_id=account['programs'][0]['program_id'],
        name='Fictional inspection fixture', business_unit_id='BU-APM', technical_requirements={'process': 'precision inspection'},
        rationale='Fit hypothesis only: potential sister-BU inspection support, subject to requirements and capability confirmation.'))
    account['rfqs'].append(synthetic_record(rfq_id=rid('rfq'), received_date=account['as_of'],
        notes='Synthetic adjacent-work inquiry. It is not a JDAM-LR component requirement or an actual buyer request.'))
    account['quotes'].append(synthetic_record(quote_id=rid('quote'), rfq_id=rid('rfq'), status='OPEN',
        current_revision_id=rid('revision'), decision_due_date=account['as_of'], notes='Internal SAMPLE scope; no real award or customer acceptance.'))
    account['quote_revisions'].append(synthetic_record(quote_revision_id=rid('revision'), quote_id=rid('quote'), revision_number=1,
        issued_date=account['as_of'], supersedes_revision_id=None, line_ids=[rid('line')], total_minor=240000,
        revision_reason='Initial synthetic adjacent inspection scope.'))
    account['quote_lines'].append(synthetic_record(quote_line_id=rid('line'), quote_revision_id=rid('revision'),
        component_id=rid('component'), quantity=2, unit_price_minor=120000, line_total_minor=240000,
        technical_requirements='Synthetic tooling dimensions and tolerance confirmation still required.'))
    account['expansion_brief'] = synthetic_record(
        public_context={'source_url': MIRROR, 'publisher': public['publisher'], 'event_date': public['event_date'],
                        'retrieval_date': public['retrieval_date'], 'assertion': public['assertion'],
                        'signal_id': 'demo-j5-boeing-public-context', 'seed_type': 'curated_monitor_style', 'synthetic': False},
        program_history=[p['program_id'] for p in account['programs']],
        supplied_component_ids=[account['components'][0]['component_id']],
        supplied_basis='Synthetic dispatch history only; no public-program supply is established.',
        active_business_units=['BU-ERA', 'BU-APM'], current_quote_id=rid('quote'),
        hypothesis='Fit hypothesis: compare the synthetic housing/inspection experience with requirements if a legitimate sourcing need is later established.',
        qualification='UNKNOWN_NEED', unsupported_link='BTX to JDAM-LR is not established by the release.',
        next_step='Research procurement scope without claiming an introduction; do not promise capacity or name a sourcing person.')
    account['commercial_case']['expansion_context'] = account['expansion_brief']
    return account
