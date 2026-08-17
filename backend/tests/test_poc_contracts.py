from datetime import UTC, datetime
from decimal import Decimal

from btx_omni.core.classification import Classification
from btx_omni.core.provenance import Provenance
from btx_omni.domain.business_units import BusinessUnit
from btx_omni.domain.crm import CrmActivity, CrmCompany, CrmContact, CrmDeal
from btx_omni.domain.evidence import SourceIdentity
from btx_omni.domain.quotes import PaperlessAccount
from btx_omni.domain.scores import ScoreAssessment, ScoreConfiguration, ScoreStatus
from btx_omni.domain.work import ActionState, WorkItem
from btx_omni.providers.sample.environment import (
    ROLE_FAMILIES,
    build_sample_environment,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _provenance() -> Provenance:
    return Provenance("sample", "record-1", None, NOW, NOW, Classification.INTERNAL_COMMERCIAL, "CONFIRMED", "SAMPLE", True)


def test_canonical_poc_domain_contracts_are_instantiable_and_source_governed() -> None:
    provenance = _provenance()
    unit = BusinessUnit("southwest", "Southwest")
    identity = SourceIdentity("hubspot", "company-1", "acct-1", provenance)
    paperless = PaperlessAccount("paperless-1", "acct-1", "Sample", provenance)
    company = CrmCompany("company-1", "acct-1", "owner-1", provenance)
    contact = CrmContact("contact-1", company.id, ROLE_FAMILIES[0], provenance)
    deal = CrmDeal("deal-1", company.id, unit.id, provenance)
    activity = CrmActivity("activity-1", company.id, NOW, provenance)
    configuration = ScoreConfiguration("config-1", "account-attractiveness-v1", True, "sample", NOW)
    assessment = ScoreAssessment("score-1", "acct-1", configuration.id, ScoreStatus.AVAILABLE, Decimal(80), Decimal(".5"), ("ev-1",), (), NOW)
    work = WorkItem("work-1", "acct-1", "Review", ActionState.PROPOSED, ("ev-1",), "owner-1")
    assert (identity.canonical_account_id, paperless.canonical_account_id, contact.company_id, deal.business_unit, activity.occurred_at, assessment.score, work.owner_id) == ("acct-1", "acct-1", "company-1", "southwest", NOW, Decimal(80), "owner-1")


def test_public_identity_and_simulated_commercial_context_keep_separate_provenance() -> None:
    sample = build_sample_environment()
    assert all(account.provenance and account.provenance.data_mode.value == "CONNECTED" and not account.provenance.synthetic for account in sample.accounts)
    assert all(context.provenance.data_mode.value == "SAMPLE" and context.provenance.synthetic for context in sample.commercial_contexts)
