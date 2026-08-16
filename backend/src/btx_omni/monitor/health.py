"""Source-operational warnings are explicitly not CommercialAlert instances."""
from __future__ import annotations

from btx_omni.monitor.contracts import SourceHealth
from btx_omni.monitor.ontology import SourceHealthState

SOURCE_HEALTH_WARNING = "SOURCE_HEALTH_WARNING"


def is_source_health_warning(health: SourceHealth) -> bool:
    return health.state in (SourceHealthState.WARNING, SourceHealthState.FAILED)
