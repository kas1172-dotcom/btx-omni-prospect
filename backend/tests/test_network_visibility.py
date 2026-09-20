from datetime import UTC, datetime

from sqlalchemy import create_engine, insert

from btx_omni.domain.work import Principal, PrincipalRole
from btx_omni.persistence import models
from btx_omni.persistence.network_import import NetworkImportRepository


def repository_with_row():
    engine = create_engine("sqlite://")
    models.metadata.create_all(engine)
    now = datetime.now(UTC)
    with engine.begin() as c:
        c.execute(insert(models.accounts).values(id="account", name="Account", relationship="PROSPECT", domain=None))
        c.execute(insert(models.network_import_batches).values(id="batch", tenant_id="tenant-a", source_kind="linkedin_connections_csv", file_sha256="a"*64, exported_at=now, imported_at=now, owner_person_id="owner", status="IMPORTED", input_row_count=1, imported_row_count=1, resolved_row_count=1, unresolved_row_count=0, data_mode="IMPORTED", visibility="owner_only", owner_user_id="seller-1"))
        c.execute(insert(models.network_people), [{"id":"owner","tenant_id":"tenant-a","kind":"internal","display_name":"Owner","profile_url":None,"batch_id":"batch"},{"id":"contact","tenant_id":"tenant-a","kind":"external","display_name":"Contact","profile_url":None,"batch_id":"batch"}])
        c.execute(insert(models.network_affiliations).values(id="aff",tenant_id="tenant-a",person_id="contact",raw_company_string="Account",raw_title="Engineer",account_id="account",resolution_method="governed_name_exact",resolution_state="RESOLVED",role_family="engineering",seniority_tier="individual",as_of=now,evidence_state="INFERRED",data_mode="IMPORTED",synthetic=False))
        c.execute(insert(models.network_ties).values(id="tie",tenant_id="tenant-a",internal_person_id="owner",external_person_id="contact",connected_on=None,batch_id="batch",tie_source="linkedin_connection_export",evidence_state="INFERRED",data_mode="IMPORTED",synthetic=False))
    return NetworkImportRepository(engine, ())


def test_visibility_denies_missing_tenant_wrong_tenant_and_non_owner():
    repo = repository_with_row()
    assert repo.visible_rows(Principal("seller-1", "Seller", PrincipalRole.SALESPERSON, None)) == ()
    assert repo.visible_rows(Principal("seller-1", "Seller", PrincipalRole.SALESPERSON, "tenant-b")) == ()
    assert repo.visible_rows(Principal("seller-2", "Seller", PrincipalRole.SALESPERSON, "tenant-a")) == ()


def test_owner_and_explicit_tenant_share_are_visible():
    repo = repository_with_row()
    assert len(repo.visible_rows(Principal("seller-1", "Seller", PrincipalRole.SALESPERSON, "tenant-a"))) == 1
    assert repo.share_batch("batch", tenant_id="tenant-a", owner_user_id="seller-1")
    assert len(repo.visible_rows(Principal("seller-2", "Seller", PrincipalRole.SALESPERSON, "tenant-a"))) == 1
