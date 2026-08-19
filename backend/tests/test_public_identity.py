from datetime import UTC, datetime

import pytest

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.accounts import (
    PublicCompanyIdentity,
    PublicIdentityField,
    PublicIdentityVerificationState,
)
from btx_omni.domain.common import DataMode, EvidenceState
from btx_omni.monitor.resolution import AccountWatchProfile, resolve_entity
from btx_omni.providers.sample.environment import build_sample_environment

NOW = datetime(2026, 8, 16, tzinfo=UTC)


def public_provenance() -> Provenance:
    return Provenance(
        "sec_edgar",
        "CIK0000000001",
        "https://data.sec.gov/submissions/CIK0000000001.json",
        NOW,
        NOW,
        Classification.PUBLIC,
        EvidenceState.CONFIRMED,
        DataMode.CONNECTED,
        False,
    )


def test_verified_public_identity_keeps_field_level_connected_provenance() -> None:
    field = PublicIdentityField(
        "0000000001",
        PublicIdentityVerificationState.VERIFIED_AUTHORITATIVE,
        public_provenance(),
        NOW,
        ("sec_cik", "0000000001"),
    )
    identity = PublicCompanyIdentity(
        PublicIdentityVerificationState.VERIFIED_AUTHORITATIVE,
        sec_cik=field,
    )

    assert identity.sec_cik and identity.sec_cik.provenance.data_mode is DataMode.CONNECTED


def test_verified_public_identity_rejects_synthetic_provenance() -> None:
    synthetic = Provenance(
        "sample",
        "record-1",
        None,
        NOW,
        NOW,
        Classification.INTERNAL_COMMERCIAL,
        EvidenceState.CONFIRMED,
        DataMode.SAMPLE,
        True,
    )

    with pytest.raises(ValueError, match="verified public identity"):
        PublicIdentityField("0000000001", PublicIdentityVerificationState.VERIFIED_AUTHORITATIVE, synthetic, NOW)


def test_researched_universe_uses_connected_public_identity_provenance() -> None:
    environment = build_sample_environment()

    assert len(environment.accounts) == len(environment.researched_accounts) > 0
    assert all(account.public_identity is not None and account.provenance and account.provenance.data_mode is DataMode.CONNECTED and not account.provenance.synthetic for account in environment.accounts)


def test_alias_subsidiary_and_ambiguous_public_resolution_remain_exact_only() -> None:
    profiles = (
        AccountWatchProfile("parent", "Verified Parent", aliases=("Former Parent",), subsidiaries=("Verified Subsidiary",)),
        AccountWatchProfile("collision", "Collision Company", aliases=("Shared Brand",)),
        AccountWatchProfile("collision-two", "Collision Two", aliases=("Shared Brand",)),
    )

    assert resolve_entity("Former Parent", profiles).canonical_account_id == "parent"
    assert resolve_entity("Verified Subsidiary", profiles).canonical_account_id == "parent"
    assert resolve_entity("Shared Brand", profiles).state.value == "AMBIGUOUS"
    assert resolve_entity("Unverified Name", profiles).state.value == "UNRESOLVED"
