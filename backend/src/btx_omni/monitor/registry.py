"""Configuration registry for generic Monitor industry packs."""
from dataclasses import dataclass

from btx_omni.monitor.ontology import EventType


@dataclass(frozen=True)
class IndustryPack:
    id: str
    enabled_event_types: tuple[EventType, ...]
    source_ids: tuple[str, ...]
    terminology: tuple[str, ...]
    program_vocabulary: tuple[str, ...] = ()
    geography_rules: tuple[str, ...] = ()
    agency_ids: tuple[str, ...] = ()
    source_identifier_kinds: tuple[str, ...] = ()
    confidence_rules: tuple[str, ...] = ()
