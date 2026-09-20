"""Actual shared projections with enhancement selected; no external services."""
from sqlalchemy import create_engine

from btx_omni.api.accounts import account_360
from btx_omni.api.runtime import PocRuntime
from btx_omni.api.today import today
from btx_omni.core.config import Settings
from btx_omni.modules.assistant.commercial_tools import CommercialToolSession
from btx_omni.persistence.models import metadata


def test_tier1_shared_projections_and_model_trace(tmp_path):
    url = f'sqlite:///{tmp_path / "enhancement.db"}'
    engine = create_engine(url)
    metadata.create_all(engine)
    engine.dispose()
    runtime = PocRuntime(Settings(_env_file=None, database_url=url, sample_enhancement_enabled=True, monitor_mode='disabled'))
    profile = account_360('boeing', runtime)
    assert profile['commercial_ledger']['record_counts']['orders'] == 1
    assert profile['commercial_ledger']['record_counts']['shipments'] == 2
    assert any(q.id == 'demo:j7:boeing:quote' for q in profile['paperless_quotes'])
    reads = CommercialToolSession(runtime.environment(), 'demo-fictional-watch')
    decision = reads.read('read_decisions', {})['customer_health']
    assert decision['score'] == 60
    assert decision['factors'][0]['contribution'] == 15
    assert decision['what_would_change_result']
    research = today(runtime)['command_center']['research_signal_briefs']
    assert any(r['id'] == 'kratos-tdi-jdam-lr-2026-08' for r in research)
    assert not any(a.id == 'kratos-tdi-jdam-lr-2026-08' for a in runtime.environment().accounts)
