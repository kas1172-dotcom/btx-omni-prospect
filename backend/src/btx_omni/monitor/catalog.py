"""Exact-only traversal catalog used by the Monitor normalizer."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from btx_omni.domain.accounts import AccountFacility
from btx_omni.domain.programs import Program
from btx_omni.monitor.contracts import EntityResolution, ProgramResolution
from btx_omni.monitor.ontology import ResolutionState
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity


def governed_phrase_in_text(phrase: str, text: str, *, allow_short: bool = False) -> bool:
    """Whole lexical phrase, not an arbitrary substring of a word or checksum.

    Bare short abbreviations in prose are insufficient company identity evidence;
    exact structured identifiers and governed publisher ownership still resolve.
    """
    if not phrase.strip() or (not allow_short and len(re.sub(r"\W", "", phrase)) <= 3):
        return False
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(token) for token in phrase.split()) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


@dataclass(frozen=True)
class MonitorCatalog:
    profiles: tuple[AccountWatchProfile, ...] = ()
    programs: tuple[Program, ...] = ()
    facilities: tuple[AccountFacility, ...] = ()

    def resolve_subjects(
        self,
        text: str,
        *,
        source_identifiers: tuple[tuple[str, str], ...] = (),
        source_url: str | None = None,
    ) -> tuple[EntityResolution, ...]:
        """Find only exact governed names/aliases appearing in source text."""
        mentions: list[str] = []
        for profile in self.profiles:
            for candidate in (
                profile.legal_name,
                *profile.aliases,
                *profile.subsidiaries,
                *profile.usaspending_recipient_names,
            ):
                if governed_phrase_in_text(candidate, text):
                    mentions.append(candidate)
                    break
        identifier_resolution = resolve_entity(
            text,
            self.profiles,
            source_identifiers=source_identifiers,
            source_url=source_url,
        )
        if identifier_resolution and identifier_resolution.state is ResolutionState.RESOLVED:
            profile = next(item for item in self.profiles if item.canonical_account_id == identifier_resolution.canonical_account_id)
            # Identifier/publisher ownership is the recorded resolution basis.
            # The entire article/JSON is evidence, never an entity display name.
            return (replace(identifier_resolution, mention=profile.legal_name),)
        resolved = [resolve_entity(mention, self.profiles) for mention in dict.fromkeys(mentions)]
        return tuple(resolved) or (
            EntityResolution("unresolved source subject", None, ResolutionState.UNRESOLVED, "no_governed_match", "source text has no exact governed account name"),
        )

    def resolve_program(self, text: str) -> ProgramResolution:
        matches = [program for program in self.programs if governed_phrase_in_text(program.name, text)]
        if len(matches) == 1:
            program = matches[0]
            return ProgramResolution(program.name, program.id, ResolutionState.RESOLVED, "canonical_program_name_exact", "exact canonical program name appears in source text")
        if len(matches) > 1:
            return ProgramResolution(None, None, ResolutionState.AMBIGUOUS, "canonical_program_name_collision", "multiple canonical program names appear in source text")
        return ProgramResolution(None, None, ResolutionState.UNRESOLVED, "no_canonical_program_name", "no exact canonical program name appears in source text")

    def resolve_facility_id(self, text: str) -> str | None:
        matches = [facility.id for facility in self.facilities if governed_phrase_in_text(facility.name, text)]
        return matches[0] if len(matches) == 1 else None

    def markets_for_account(self, account_id: str | None) -> tuple[str, ...]:
        profile = next((item for item in self.profiles if item.canonical_account_id == account_id), None)
        return profile.industries if profile else ()
