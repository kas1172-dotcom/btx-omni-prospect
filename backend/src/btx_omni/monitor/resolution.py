"""Exact identifiers and governed aliases take precedence over optional AI assistance."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

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
    usaspending_recipient_names: tuple[str, ...] = ()
    usaspending_recipient_sources: tuple[tuple[str, str], ...] = ()


_CORPORATE_SUFFIXES = frozenset({"inc", "incorporated", "corp", "corporation", "llc", "ltd", "limited", "plc", "co", "company"})


def normalize_governed_name(value: str) -> str:
    """Conservative deterministic comparison form; it is never a fuzzy score."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    tokens = re.findall(r"[\w]+", normalized, flags=re.UNICODE)
    while tokens and tokens[-1] in _CORPORATE_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def _host(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").casefold().removeprefix("www.") or None


def _distinct(matches: list[AccountWatchProfile]) -> list[AccountWatchProfile]:
    return list({profile.canonical_account_id: profile for profile in matches}.values())


def resolve_entity(mention: str, profiles: tuple[AccountWatchProfile, ...], *, source_identifiers: tuple[tuple[str, str], ...] = (), source_url: str | None = None) -> EntityResolution:
    """Resolve only governed evidence and return ambiguity instead of guessing."""
    identifier_matches = _distinct([
        profile for profile in profiles
        if any(
            pair in profile.source_native_identifiers
            or (pair[0].casefold() in {"uei", "cage", "sec_cik", "cik"} and pair[1].lstrip("0").casefold() in {str(value or "").lstrip("0").casefold() for value in (profile.uei, profile.cage, profile.sec_cik)})
            for pair in source_identifiers
        )
    ])
    if len(identifier_matches) == 1:
        profile = identifier_matches[0]
        return EntityResolution(mention, profile.canonical_account_id, ResolutionState.RESOLVED, "source_native_identifier_exact", "exact governed identifier")
    if len(identifier_matches) > 1:
        return EntityResolution(
            mention,
            None,
            ResolutionState.AMBIGUOUS,
            "source_native_identifier_collision",
            "multiple governed accounts match supplied exact source identifiers",
            tuple(profile.canonical_account_id for profile in identifier_matches),
        )
    source_owners = _distinct([
        profile for profile in profiles
        if ("governed_source_owner", profile.canonical_account_id) in source_identifiers
    ])
    if len(source_owners) == 1:
        profile = source_owners[0]
        return EntityResolution(mention, profile.canonical_account_id, ResolutionState.RESOLVED, "governed_source_ownership", "source publisher is explicitly governed as owned by this account")
    if len(source_owners) > 1:
        return EntityResolution(mention, None, ResolutionState.AMBIGUOUS, "governed_source_ownership_collision", "multiple governed source owners were supplied", tuple(profile.canonical_account_id for profile in source_owners))
    exact = mention.casefold().strip()
    matches = _distinct([profile for profile in profiles if exact in {
        profile.legal_name.casefold(),
        *(alias.casefold() for alias in profile.aliases),
        *(subsidiary.casefold() for subsidiary in profile.subsidiaries),
        *(name.casefold() for name in profile.usaspending_recipient_names),
    }])
    if len(matches) == 1:
        return EntityResolution(mention, matches[0].canonical_account_id, ResolutionState.RESOLVED, "governed_name_exact", "exact governed legal name, alias, subsidiary, or source recipient name")
    if len(matches) > 1:
        return EntityResolution(mention, None, ResolutionState.AMBIGUOUS, "governed_alias_collision", "multiple governed accounts share the mention", tuple(profile.canonical_account_id for profile in matches))
    source_host = _host(source_url)
    owned = _distinct([
        profile for profile in profiles
        if source_host and source_host in {
            _host(profile.domain), _host(profile.newsroom_url), _host(profile.investor_relations_url),
            *(_host(url) for url in profile.official_feed_urls),
        }
    ])
    if len(owned) == 1:
        return EntityResolution(mention, owned[0].canonical_account_id, ResolutionState.RESOLVED, "governed_source_ownership", "source URL is governed as the account's official domain")
    if len(owned) > 1:
        return EntityResolution(mention, None, ResolutionState.AMBIGUOUS, "governed_source_ownership_collision", "source ownership maps to multiple governed accounts", tuple(profile.canonical_account_id for profile in owned))
    normalized = normalize_governed_name(mention)
    normalized_matches = _distinct([profile for profile in profiles if normalized and normalized in {
        normalize_governed_name(profile.legal_name),
        *(normalize_governed_name(alias) for alias in profile.aliases),
        *(normalize_governed_name(subsidiary) for subsidiary in profile.subsidiaries),
        *(normalize_governed_name(name) for name in profile.usaspending_recipient_names),
    }])
    if len(normalized_matches) == 1:
        return EntityResolution(mention, normalized_matches[0].canonical_account_id, ResolutionState.RESOLVED, "governed_name_normalized", "unambiguous safe normalization of governed name")
    if len(normalized_matches) > 1:
        return EntityResolution(mention, None, ResolutionState.AMBIGUOUS, "governed_name_normalization_collision", "safe normalization maps to multiple governed accounts", tuple(profile.canonical_account_id for profile in normalized_matches))
    return EntityResolution(mention, None, ResolutionState.UNRESOLVED, "no_governed_match", "no governed identifier, name, source ownership, or unambiguous normalized name")
