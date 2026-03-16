# Unit tests for app/services/decision.py

import pytest
from app.schemas import InvoiceReviewRequest
from app.services.decision import (
    evaluate_invoice,
    parse_threshold,
    PASS,
    FAIL,
    NEEDS_INFO,
    DEFAULT_THRESHOLD,
    SUPPORTED_CURRENCIES,
)


# Helper Functions 
def make_invoice(**kwargs) -> InvoiceReviewRequest:
    """
    Returns a fully valid invoice by default.
    Pass keyword arguments to override specific fields.
    """
    defaults = {
        "invoice_number": "INV-001",
        "vendor_name":    "Acme GmbH",
        "total_amount":   500.0,
        "currency":       "EUR",
        "invoice_date":   "2026-01-15",
        "customer_name":  "Beta Corp",
        "due_date":       "2026-03-30",
        "rules_text":     None,
    }
    defaults.update(kwargs)
    return InvoiceReviewRequest(**defaults)


# parse_threshold tests
class TestParseThreshold:
    """Tests for the rules_text threshold parser."""

    def test_returns_default_when_rules_text_is_none(self):
        assert parse_threshold(None) == DEFAULT_THRESHOLD

    def test_returns_default_when_rules_text_is_empty(self):
        assert parse_threshold("") == DEFAULT_THRESHOLD

    def test_returns_default_when_no_max_amount_pattern(self):
        assert parse_threshold("some random rules without a number") == DEFAULT_THRESHOLD

    def test_parses_integer_threshold(self):
        assert parse_threshold("max_amount=5000") == 5000.0

    def test_parses_float_threshold(self):
        assert parse_threshold("max_amount=2500.75") == 2500.75

    def test_parses_threshold_with_spaces_around_equals(self):
        assert parse_threshold("max_amount = 3000") == 3000.0

    def test_parses_threshold_embedded_in_longer_text(self):
        assert parse_threshold("Vendor approved. max_amount=8000. No exceptions.") == 8000.0

    def test_returns_default_for_malformed_value(self):
        assert parse_threshold("max_amount=abc") == DEFAULT_THRESHOLD


# PASS cases
class TestPassDecision:
    """All required fields present and within limits = PASS."""

    def test_valid_invoice_returns_pass(self):
        decision, reasons, evidence = evaluate_invoice(make_invoice())
        assert decision == PASS

    def test_pass_reason_is_informative(self):
        _, reasons, _ = evaluate_invoice(make_invoice())
        assert len(reasons) == 1
        assert "All required fields" in reasons[0]

    def test_pass_evidence_contains_expected_keys(self):
        _, _, evidence = evaluate_invoice(make_invoice())
        assert "invoice_number_present" in evidence
        assert "total_amount" in evidence
        assert "currency" in evidence
        assert "threshold" in evidence
        assert "vendor_name_present" in evidence

    def test_pass_with_usd_currency(self):
        decision, _, _ = evaluate_invoice(make_invoice(currency="USD"))
        assert decision == PASS

    def test_pass_with_amount_exactly_at_threshold(self):
        decision, _, _ = evaluate_invoice(make_invoice(total_amount=1000.0))
        assert decision == PASS

    def test_pass_with_custom_threshold_from_rules_text(self):
        decision, _, evidence = evaluate_invoice(
            make_invoice(total_amount=1500.0, rules_text="max_amount=2000")
        )
        assert decision == PASS
        assert evidence["threshold"] == 2000.0

    def test_optional_fields_can_be_missing_on_pass(self):
        decision, _, _ = evaluate_invoice(
            make_invoice(invoice_date=None, customer_name=None, due_date=None)
        )
        assert decision == PASS


# FAIL cases
class TestFailDecision:
    """Missing invoice_number is the only hard FAIL condition."""

    def test_missing_invoice_number_returns_fail(self):
        decision, _, _ = evaluate_invoice(make_invoice(invoice_number=None))
        assert decision == FAIL

    def test_empty_string_invoice_number_returns_fail(self):
        decision, _, _ = evaluate_invoice(make_invoice(invoice_number=""))
        assert decision == FAIL

    def test_whitespace_only_invoice_number_returns_fail(self):
        decision, _, _ = evaluate_invoice(make_invoice(invoice_number="   "))
        assert decision == FAIL

    def test_fail_reason_mentions_invoice_number(self):
        _, reasons, _ = evaluate_invoice(make_invoice(invoice_number=None))
        assert any("invoice_number" in r for r in reasons)

    def test_fail_beats_needs_info_when_both_triggered(self):
        decision, reasons, _ = evaluate_invoice(
            make_invoice(invoice_number=None, total_amount=None)
        )
        assert decision == FAIL
        assert len(reasons) == 2

    def test_fail_beats_needs_info_with_missing_currency_too(self):
        decision, reasons, _ = evaluate_invoice(
            make_invoice(invoice_number=None, currency=None, total_amount=None)
        )
        assert decision == FAIL
        assert len(reasons) == 3


# NEEDS_INFO cases
class TestNeedsInfoDecision:

    def test_missing_total_amount_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(total_amount=None))
        assert decision == NEEDS_INFO

    def test_missing_currency_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(currency=None))
        assert decision == NEEDS_INFO

    def test_empty_currency_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(currency=""))
        assert decision == NEEDS_INFO

    def test_missing_vendor_name_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(vendor_name=None))
        assert decision == NEEDS_INFO

    def test_empty_vendor_name_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(vendor_name=""))
        assert decision == NEEDS_INFO

    def test_unsupported_currency_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(currency="GBP"))
        assert decision == NEEDS_INFO

    def test_unsupported_currency_reason_is_informative(self):
        _, reasons, _ = evaluate_invoice(make_invoice(currency="GBP"))
        assert any("GBP" in r for r in reasons)
        assert any("EUR" in r or "USD" in r for r in reasons)

    def test_amount_exceeds_default_threshold_returns_needs_info(self):
        decision, _, _ = evaluate_invoice(make_invoice(total_amount=1000.01))
        assert decision == NEEDS_INFO

    def test_amount_exceeds_custom_threshold_returns_needs_info(self):
        decision, _, evidence = evaluate_invoice(
            make_invoice(total_amount=3000.0, rules_text="max_amount=2000")
        )
        assert decision == NEEDS_INFO
        assert evidence["threshold"] == 2000.0

    def test_multiple_needs_info_rules_all_collected(self):
        _, reasons, _ = evaluate_invoice(
            make_invoice(currency=None, vendor_name=None)
        )
        assert len(reasons) == 2
        assert any("currency" in r for r in reasons)
        assert any("vendor_name" in r for r in reasons)


# Evidence tests 
class TestEvidence:
    """Evidence should accurately reflect the invoice data that was evaluated."""

    def test_evidence_reflects_actual_amount(self):
        _, _, evidence = evaluate_invoice(make_invoice(total_amount=750.0))
        assert evidence["total_amount"] == 750.0

    def test_evidence_reflects_actual_currency(self):
        _, _, evidence = evaluate_invoice(make_invoice(currency="USD"))
        assert evidence["currency"] == "USD"

    def test_evidence_invoice_number_present_true_when_provided(self):
        _, _, evidence = evaluate_invoice(make_invoice(invoice_number="INV-999"))
        assert evidence["invoice_number_present"] is True

    def test_evidence_invoice_number_present_false_when_missing(self):
        _, _, evidence = evaluate_invoice(make_invoice(invoice_number=None))
        assert evidence["invoice_number_present"] is False

    def test_evidence_uses_default_threshold_when_no_rules_text(self):
        _, _, evidence = evaluate_invoice(make_invoice(rules_text=None))
        assert evidence["threshold"] == DEFAULT_THRESHOLD

    def test_evidence_uses_custom_threshold_when_rules_text_present(self):
        _, _, evidence = evaluate_invoice(make_invoice(rules_text="max_amount=3000"))
        assert evidence["threshold"] == 3000.0