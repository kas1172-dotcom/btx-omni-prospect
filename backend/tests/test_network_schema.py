from btx_omni.core.provenance import Provenance
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.core.classification import Classification
from datetime import UTC, datetime
import pytest


def test_imported_provenance_is_real_and_cannot_be_synthetic():
    now = datetime.now(UTC)
    value = Provenance("network_import", "batch", None, now, now, Classification.INTERNAL_COMMERCIAL, EvidenceState.INFERRED, DataMode.IMPORTED, False)
    assert value.data_mode is DataMode.IMPORTED
    with pytest.raises(ValueError, match="cannot be synthetic"):
        Provenance("network_import", "batch", None, now, now, Classification.INTERNAL_COMMERCIAL, EvidenceState.INFERRED, DataMode.IMPORTED, True)
