"""Exact-only traversal catalog used by the Monitor normalizer."""
from __future__ import annotations

from dataclasses import dataclass

from btx_omni.domain.accounts import AccountFacility
from btx_omni.domain.programs import Program
from btx_omni.monitor.contracts import EntityResolution, ProgramResolution
from btx_omni.monitor.ontology import ResolutionState
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity


@dataclass(frozen=True)
class MonitorCatalog:
    profiles: tuple[AccountWatchProfile, ...] = ()
    programs: tuple[Program, ...] = ()
    facilities: tuple[AccountFacility, ...] = ()

    def resolve_subjects(self, text: str) -> tuple[EntityResolution, ...]:
        """Find only exact governed names/aliases appearing in source text."""
        normalized = text.casefold()
        mentions: list[str] = []
        for profile in self.profiles:
            for candidate in (profile.legal_name, *profile.aliases, *profile.subsidiaries):
                if candidate and candidate.casefold() in normalized:
                    mentions.append(candidate)
                    break
        resolved = [resolve_entity(mention, self.profiles) for mention in dict.fromkeys(mentions)]
        return tuple(resolved) or (
            EntityResolution("unresolved source subject", None, ResolutionState.UNRESOLVED, "no_governed_match", "source text has no exact governed account name"),
        )

    def resolve_program(self, text: str) -> ProgramResolution:
        matches = [program for program in self.programs if program.name.casefold() in text.casefold()]
        if len(matches) == 1:
            program = matches[0]
            return ProgramResolution(program.name, program.id, ResolutionState.RESOLVED, "canonical_program_name_exact", "exact canonical program name appears in source text")
        if len(matches) > 1:
            return ProgramResolution(None, None, ResolutionState.AMBIGUOUS, "canonical_program_name_collision", "multiple canonical program names appear in source text")
        return ProgramResolution(None, None, ResolutionState.UNRESOLVED, "no_canonical_program_name", "no exact canonical program name appears in source text")

    def resolve_facility_id(self, text: str) -> str | None:
        matches = [facility.id for facility in self.facilities if facility.name.casefold() in text.casefold()]
        return matches[0] if len(matches) == 1 else None

    def markets_for_account(self, account_id: str | None) -> tuple[str, ...]:
        profile = next((item for item in self.profiles if item.canonical_account_id == account_id), None)
        return profile.industries if profile else ()
