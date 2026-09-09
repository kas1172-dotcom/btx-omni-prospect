from btx_omni.modules.commercial.map_context import map_commercial_context


def test_map_facets_preserve_naics_assumptions_and_use_governed_bu_crosswalk():
    naics = [{"code": "334516", "taxonomy_version": "2022", "scope": "ACCOUNT_POC_CLASSIFICATION", "verification": "ASSUMED_NOT_REGISTRY_VERIFIED"}]
    result = map_commercial_context({"naics_assignments": naics, "components": [{"business_unit_id": "BU-GENELMEC"}, {"business_unit_id": "BU-GENELMEC"}, {"business_unit_id": "ungoverned"}]})
    assert result["naics_assignments"] == naics
    assert result["commercial_business_unit_ids"] == ["gen-el-mec"]
    assert result["commercial_context_scope"] == "ACCOUNT_SCENARIO_NOT_CUSTOMER_SITE_QUALIFICATION"
    assert "capacity" not in result and "site_capabilities" not in result


def test_missing_commercial_context_does_not_fabricate_classifications():
    assert map_commercial_context(None) == {"naics_assignments": [], "commercial_business_unit_ids": [], "commercial_context_scope": "UNAVAILABLE"}


def test_fulfillment_facets_reuse_actual_obligations_and_do_not_claim_available_capacity():
    from test_commercial_persistence import importer_package
    account = importer_package()['accounts'][0]
    value = map_commercial_context(account, canonical_account_id='honeywell', revision='r1')['fulfillment_attention']
    assert value['states'] == ['ACCEPTANCE_PENDING', 'MISSED_COMMITMENT', 'OPEN_SHIPMENT']
    assert value['order_line_ids'] == ['ol']
    assert value['revision'] == 'r1' and value['as_of'] == account['as_of']
    assert value['scope'] == 'ACCOUNT_COMMERCIAL_HISTORY_NOT_SITE_CAPACITY'
