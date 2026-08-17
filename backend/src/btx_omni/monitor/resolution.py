"""Exact identifiers and governed aliases take precedence over optional AI assistance."""
from __future__ import annotations

from dataclasses import dataclass

from btx_omni.monitor.contracts import EntityResolution
from btx_omni.monitor.ontology import ResolutionState


@dataclass(frozen=True)
class AccountWatchProfile:
    canonical_account_id: str
    legal_name: str
    aliases: tuple[str, ...] = ()
    subsidiaries: tuple[str, ...] = ()
    domain: str | None = None
    newsroom_url: str | None = None
    investor_relations_url: str | None = None
    sec_cik: str | None = None
    uei: str | None = None
    cage: str | None = None
    source_native_identifiers: tuple[tuple[str, str], ...] = ()
    facilities: tuple[str, ...] = ()
    programs: tuple[str, ...] = ()
    industries: tuple[str, ...] = ()
    official_feed_urls: tuple[str, ...] = ()


def resolve_entity(mention: str, profiles: tuple[AccountWatchProfile, ...], *, source_identifiers: tuple[tuple[str, str], ...] = ()) -> EntityResolution:
    normalized = mention.casefold().strip()
    identifier_matches = [profile for profile in profiles if any(pair in profile.source_native_identifiers or pair[1] in (profile.uei, profile.cage, profile.sec_cik) for pair in source_identifiers)]
    if len(identifier_matches) == 1:
        profile = identifier_matches[0]
        return EntityResolution(mention, profile.canonical_account_id, ResolutionState.RESOLVED, "source_native_identifier_exact", "exact governed identifier")
    matches = [profile for profile in profiles if normalized in {profile.legal_name.casefold(), *(alias.casefold() for alias in profile.aliases), *(subsidiary.casefold() for subsidiary in profile.subsidiaries)}]
    if len(matches) == 1:
        return EntityResolution(mention, matches[0].canonical_account_id, ResolutionState.RESOLVED, "governed_alias_exact", "exact legal name, alias, or subsidiary")
    if len(matches) > 1:
        return EntityResolution(mention, None, ResolutionState.AMBIGUOUS, "governed_alias_collision", "multiple governed accounts share the mention", tuple(profile.canonical_account_id for profile in matches))
    return EntityResolution(mention, None, ResolutionState.UNRESOLVED, "no_governed_match", "no exact identifier or alias")
