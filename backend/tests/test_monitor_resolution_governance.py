from btx_omni.monitor.ontology import ResolutionState
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity

PROFILES = (
    AccountWatchProfile(
        "acme",
        "Acme Aerospace Corporation",
        aliases=("Acme Aero",),
        subsidiaries=("Acme Precision Systems",),
        domain="acme.example",
        newsroom_url="https://news.acme.example/releases",
        sec_cik="0000123456",
        uei="UEI-ACME-01",
        cage="1A2B3",
        usaspending_recipient_names=("Acme Aerospace Corp.",),
    ),
    AccountWatchProfile("acme-precision", "Acme Precision, Inc.", domain="precision.example"),
)


def test_governed_resolution_evidence_hierarchy_and_safe_normalization() -> None:
    assert resolve_entity("unrelated", PROFILES, source_identifiers=(("sec_cik", "123456"),)).canonical_account_id == "acme"
    assert resolve_entity("Acme Aerospace Corporation", PROFILES).canonical_account_id == "acme"
    assert resolve_entity("Acme Aero", PROFILES).canonical_account_id == "acme"
    assert resolve_entity("Acme Precision Systems", PROFILES).canonical_account_id == "acme"
    assert resolve_entity("Acme Aerospace Corp.", PROFILES).canonical_account_id == "acme"
    assert resolve_entity("ACME AEROSPACE, CORPORATION", PROFILES).canonical_account_id == "acme"
    assert resolve_entity("unrelated release", PROFILES, source_url="https://news.acme.example/releases/1").canonical_account_id == "acme"


def test_authoritative_identifier_wins_and_ambiguous_or_unknown_names_never_merge() -> None:
    assert resolve_entity("Acme Precision", PROFILES, source_identifiers=(("uei", "UEI-ACME-01"),)).canonical_account_id == "acme"
    ambiguous = resolve_entity("Acme Aerospace", (PROFILES[0], AccountWatchProfile("other", "Acme Aerospace, Inc.")))
    assert ambiguous.state is ResolutionState.AMBIGUOUS
    assert resolve_entity("Totally Unrelated Manufacturing", PROFILES).state is ResolutionState.UNRESOLVED


def test_identifier_collisions_are_explicitly_ambiguous() -> None:
    collision = (*PROFILES, AccountWatchProfile("other", "Other", uei="UEI-ACME-01"))
    assert resolve_entity("Other", collision, source_identifiers=(("uei", "UEI-ACME-01"),)).state is ResolutionState.AMBIGUOUS
