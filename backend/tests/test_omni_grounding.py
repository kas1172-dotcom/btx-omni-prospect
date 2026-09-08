import pytest

from btx_omni.modules.assistant.grounding import synthesis_rejection


@pytest.mark.parametrize("text, reason", [
    ("PWIN is 99%.", "UNSUPPORTED_NUMERIC_CLAIM"),
    ("I sent the recovery email.", "UNSUPPORTED_EXECUTION_CLAIM"),
    ("The HubSpot record was updated.", "UNSUPPORTED_EXECUTION_CLAIM"),
    ("Capacity is confirmed.", "CONTRADICTED_CONSTRAINT"),
    ("Revenue was -400.", "UNSUPPORTED_NUMERIC_CLAIM"),
    ("Amount " + "9" * 1000, "INVALID_NUMERIC_CLAIM"),
])
def test_unfounded_numeric_execution_and_constraint_claims_rejected(text, reason):
    assert synthesis_rejection(text, 'Revenue 400. {"quoted_value_minor": 12300}. Delivery remains constrained.', blocking_constraints=True) == reason


def test_exact_currency_conversion_rounding_and_list_formatting_are_supported():
    source = '{"quoted_value_minor": 12300, "score": 51.77123}. No external write occurred.'
    assert synthesis_rejection("1. Quote is USD 123.00.\n2. Index is 51.77, not a probability. No external write occurred.", source) is None


def test_record_identifier_digits_are_neither_fake_financial_claims_nor_amount_authority():
    source = '{"record_id": "INV-NOT-IN-BTX-9127", "status": "NOT_FOUND_IN_ACCOUNT", "record": null}'
    assert synthesis_rejection('Invoice INV-NOT-IN-BTX-9127 is not available in this account. Its payment date is unknown.', source) is None
    assert synthesis_rejection('Its amount is USD 9127.', source) == 'UNSUPPORTED_NUMERIC_CLAIM'
    assert synthesis_rejection('Invoice INV-NOT-IN-BTX-8234 is paid.', source) == 'UNSUPPORTED_NUMERIC_CLAIM'
    assert synthesis_rejection('No match for INV-NOT-IN-BTX-9127. Its payment date is unknown.', source) is None
    assert synthesis_rejection('No match for INV-NOT-IN-BTX-9127.1.', source) == 'UNSUPPORTED_NUMERIC_CLAIM'


def test_raw_minor_units_never_authorize_hundredfold_major_currency_claim():
    source = '{"currency": "USD", "revenue_minor": 426489532, "bookings_minor": 433981632}'
    assert synthesis_rejection('Revenue is USD 426,489,532.', source) == 'UNSUPPORTED_NUMERIC_CLAIM'
    assert synthesis_rejection('Revenue is USD 4,264,895.32; bookings USD 4,339,816.32.', source) is None
