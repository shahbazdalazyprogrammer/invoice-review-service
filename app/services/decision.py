from __future__ import annotations
import re
import logging
from typing import Any
from app.schemas import InvoiceReviewRequest

logger = logging.getLogger(__name__)

# Constants
DEFAULT_THRESHOLD: float = 1000.0
SUPPORTED_CURRENCIES: set[str] = {"EUR", "USD"}

# Decision constants
PASS       = "PASS"
FAIL       = "FAIL"
NEEDS_INFO = "NEEDS_INFO"


# Threshold parser
def parse_threshold(rules_text: str | None) -> float:
    """
    Extracts a numeric threshold from rules_text if present.

    Supported format:  max_amount=5000
    Falls back to DEFAULT_THRESHOLD if not found or unparseable.

    Example:
        parse_threshold("max_amount=5000")  =  5000.0
        parse_threshold(None)               =  1000.0
        parse_threshold("some random text") =  1000.0
    """
    if not rules_text:
        return DEFAULT_THRESHOLD

    match = re.search(r"max_amount\s*=\s*([0-9]+(?:\.[0-9]+)?)", rules_text)
    if match:
        try:
            value = float(match.group(1))
            logger.info("Parsed custom threshold from rules_text: %s", value)
            return value
        except ValueError:
            pass

    return DEFAULT_THRESHOLD


# Core decision function
def evaluate_invoice(
    invoice: InvoiceReviewRequest,
) -> tuple[str, list[str], dict[str, Any]]:
    """
    Applies deterministic rules to an invoice and returns a decision.

    Returns:
        decision: one of PASS, FAIL, NEEDS_INFO
        reasons : list of human-readable strings explaining the decision
        evidence: dict of key fields and values used in the decision

    Rules (in priority order):
        1. Missing invoice_number = FAIL
        2. Missing total_amount = NEEDS_INFO
        3. Missing currency  = NEEDS_INFO
        4. Missing vendor_name = NEEDS_INFO
        5. Unsupported currency = NEEDS_INFO
        6. total_amount exceeds threshold = NEEDS_INFO
        7. All checks pass = PASS
    """
    reasons:  list[str]       = []
    evidence: dict[str, Any]  = {}
    decision: str             = PASS   # optimistic default; rules downgrade it

    threshold = parse_threshold(invoice.rules_text)

    # Build evidence snapshot
    # Record what we checked regardless of outcome
    # and for the reviewer to understand exactly what data drove the decision.
    evidence["invoice_number_present"] = bool(invoice.invoice_number)
    evidence["vendor_name_present"]    = bool(invoice.vendor_name)
    evidence["total_amount"]           = invoice.total_amount
    evidence["currency"]               = invoice.currency
    evidence["threshold"]              = threshold

    # Rule 1: invoice_number is mandatory
    # A document with no identifier cannot be reviewed at all = FAIL.
    if not invoice.invoice_number or not invoice.invoice_number.strip():
        reasons.append("invoice_number is missing or empty: cannot process invoice without a unique identifier.")
        decision = FAIL

    # Rule 2: total_amount must be present
    if invoice.total_amount is None:
        reasons.append("total_amount is missing: cannot assess invoice value.")
        decision = _downgrade_to(decision, NEEDS_INFO)

    # Rule 3: currency must be present
    if not invoice.currency or not invoice.currency.strip():
        reasons.append("currency is missing: required to validate the invoice amount.")
        decision = _downgrade_to(decision, NEEDS_INFO)

    # Rule 4: vendor_name must be present
    if not invoice.vendor_name or not invoice.vendor_name.strip():
        reasons.append("vendor_name is missing: cannot identify the issuing party.")
        decision = _downgrade_to(decision, NEEDS_INFO)

    # Rule 5: currency must be supported 
    if invoice.currency and invoice.currency.strip().upper() not in SUPPORTED_CURRENCIES:
        reasons.append(
            f"currency '{invoice.currency}' is not supported. "
            f"Accepted values: {sorted(SUPPORTED_CURRENCIES)}."
        )
        decision = _downgrade_to(decision, NEEDS_INFO)

    # Rule 6: amount must not exceed threshold 
    if invoice.total_amount is not None and invoice.total_amount > threshold:
        reasons.append(
            f"total_amount {invoice.total_amount} exceeds the configured "
            f"threshold of {threshold}. Manual review required."
        )
        decision = _downgrade_to(decision, NEEDS_INFO)

    # Rule 7: all good 
    if decision == PASS:
        reasons.append("All required fields are present and values are within limits.")

    logger.info("Decision reached: %s | Reasons: %s", decision, reasons)
    return decision, reasons, evidence


# Helper Functions

def _downgrade_to(current: str, candidate: str) -> str:
    """
    Applies decision priority: FAIL > NEEDS_INFO > PASS.
    Once a FAIL is set, nothing can override it.

    This ensures multiple rules can fire and the worst outcome wins.
    """
    priority = {PASS: 0, NEEDS_INFO: 1, FAIL: 2}
    if priority.get(candidate, 0) > priority.get(current, 0):
        return candidate
    return current