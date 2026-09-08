from dataclasses import replace
from datetime import UTC, datetime, timedelta

from btx_omni.domain.alerts import CommercialAlertKind
from btx_omni.domain.quotes import QuoteStatus
from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.modules.alerts.commercial import CommercialAlertEngine
from btx_omni.modules.work.service import WorkService
from btx_omni.modules.work.suggestions import project_suggestions
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def alerts():
    sample = build_sample_environment()
    return CommercialAlertEngine().evaluate(sample.commercial_contexts, sample.quotes, observed_at=NOW, orders=sample.orders)


def test_suggestion_identity_is_independent_of_enumeration_and_duplicate_replay():
    source = alerts()
    first = project_suggestions(source)
    assert first == project_suggestions(tuple(reversed(source)))
    assert first == project_suggestions(source + source)
    isolated = project_suggestions((source[0],))[0]
    assert next(item for item in first if item['source_alert_id'] == source[0].id)['id'] == isolated['id']
    assert all(item['id'].startswith('suggestion-v2-') for item in first)
    modified = replace(source[0], severity='LOW' if source[0].severity != 'LOW' else 'HIGH')
    correction = project_suggestions((modified,))[0]
    assert correction['id'] == isolated['id'] and correction['revision'] != isolated['revision']


def test_quote_alerts_preserve_parallel_quotes_and_do_not_attach_another_bu():
    sample = build_sample_environment()
    context = sample.commercial_contexts[0]
    source = sample.quotes[0]
    quote = replace(source, id='quote-one', account_id=context.account_id, business_unit=context.business_unit,
                    business_unit_ids=(context.business_unit,), status=QuoteStatus.OPEN,
                    quoted_at=(NOW - timedelta(days=70)).date(), value_minor=100000)
    other = replace(context, business_unit='unrelated-bu', provenance=replace(context.provenance, source_record_id='other-context'))
    second = replace(quote, id='quote-two', provenance=replace(quote.provenance, source_record_id='quote-two'))
    result = CommercialAlertEngine().evaluate((context, other), (quote, second), observed_at=NOW)
    quote_alerts = [item for item in result if item.type == CommercialAlertKind.STALE_QUOTE]
    assert len(quote_alerts) == 2 and len({item.id for item in quote_alerts}) == 2
    assert {item.subject_id for item in quote_alerts} == {'quote-one', 'quote-two'}
    assert all(item.business_unit == context.business_unit for item in quote_alerts)
    multi = replace(quote, business_unit='MULTIPLE_BUSINESS_UNITS', business_unit_ids=(context.business_unit, 'unrelated-bu'))
    multi_alerts = CommercialAlertEngine().evaluate((context, other), (multi,), observed_at=NOW)
    assert {item.business_unit for item in multi_alerts if item.type == CommercialAlertKind.STALE_QUOTE} == {context.business_unit, 'unrelated-bu'}


def test_legacy_work_requires_exact_account_kind_and_evidence_not_old_index():
    alert = next(item for item in alerts() if item.type == CommercialAlertKind.STALE_QUOTE)
    work = WorkService()
    principal = Principal('seller', 'Seller', PrincipalRole.SALESPERSON)
    old_id = f'alert-{alert.type.value.lower()}-{alert.account_id}-{alert.business_unit}:999'
    existing = work.create(account_id=alert.account_id, title='User-edited task title', occurred_at=NOW,
                           principal=principal, evidence_ids=alert.evidence_ids, source_suggestion_id=old_id)
    projected = project_suggestions((alert,), actions=(existing,), visible_action_ids={existing.id})[0]
    assert projected['converted_action_id'] == existing.id and projected['legacy_work_match']
    unrelated = replace(existing, evidence_ids=('another-quote',))
    assert project_suggestions((alert,), actions=(unrelated,), visible_action_ids={existing.id})[0]['converted_action_id'] is None
    hidden = project_suggestions((alert,), actions=(existing,), visible_action_ids=set())[0]
    assert hidden['converted_action_id'] is None and hidden['conversion_blocked']
    ambiguous = project_suggestions((alert,), actions=(existing, replace(existing, id='another-action')),
                                    visible_action_ids={existing.id, 'another-action'})[0]
    assert ambiguous['conversion_blocked'] and ambiguous['converted_action_id'] is None
