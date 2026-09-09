import pytest
from sqlalchemy import create_engine

from btx_omni.persistence.ai_usage import AiUsageRepository, ai_call_receipts


@pytest.fixture
def ai_usage(tmp_path):
    """Real accounting persistence for injected SDK fixtures; no budget bypass."""
    engine = create_engine(f'sqlite:///{tmp_path / "ai-usage.db"}')
    ai_call_receipts.create(engine)
    yield AiUsageRepository(engine)
    engine.dispose()
