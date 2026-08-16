"""Stage A plausibility filter; commercial matching remains downstream."""
from dataclasses import dataclass

from btx_omni.monitor.contracts import IntelligenceEvent
from btx_omni.monitor.registry import IndustryPack


@dataclass(frozen=True)
class MonitorPipeline:
    pack: IndustryPack

    def plausible(self, event: IntelligenceEvent) -> bool:
        return event.event_type in self.pack.enabled_event_types and bool(event.subject_entities)

    def output_for_matching(self, event: IntelligenceEvent) -> IntelligenceEvent | None:
        return event if self.plausible(event) else None
