from decimal import Decimal

from btx_omni.core.clock import as_of_datetime
from btx_omni.monitor.briefs import signal_brief
from btx_omni.providers.sample.risk_cases import risk_context


def test_j6_unconfirmed_risk_requires_validation_and_confirmed_risk_escalates():
    for confidence, target, disposition in [('LOW', '37.75', 'VALIDATE_IMMEDIATELY'), ('HIGH', '88.75', 'ESCALATE_NOW')]:
        brief = signal_brief(*risk_context(confidence=confidence), freshness_hours=720, now=as_of_datetime())
        assert brief.risk_severity['score'] == Decimal('76.25')
        assert brief.signal_confidence['score'] == Decimal(target)
        assert brief.risk_severity['disposition'] == disposition
        assert brief.seed_context['seed_type'] == 'curated_monitor_style'
        assert brief.seed_context['synthetic']
        assert brief.seed_context['mitigation_notes'] and brief.seed_context['open_applicability_questions']
        if confidence == 'LOW':
            assert 'UNCONFIRMED' in brief.what_happened
