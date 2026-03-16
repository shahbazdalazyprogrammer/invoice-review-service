"""
API integration tests for the Invoice Review Service.
Fixtures are defined in conftest.py.
"""
import pytest
from fastapi.testclient import TestClient

# Shared payloads 
VALID_INVOICE = {
    "invoice_number": "INV-001",
    "vendor_name":    "Acme GmbH",
    "total_amount":   500.0,
    "currency":       "EUR",
    "invoice_date":   "2026-01-15",
    "customer_name":  "Beta Corp",
    "due_date":       "2026-03-30",
}

FAIL_INVOICE = {
    "vendor_name":  "Acme GmbH",
    "total_amount": 500.0,
    "currency":     "EUR",
}

NEEDS_INFO_INVOICE = {
    "invoice_number": "INV-002",
    "vendor_name":    "Acme GmbH",
    "total_amount":   9999.0,
    "currency":       "EUR",
}


# GET /health 
class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_status(self, client):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


# POST /reviews 
class TestPostReviews:

    def test_valid_invoice_returns_201(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        assert response.status_code == 201

    def test_valid_invoice_returns_pass(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        assert response.json()["decision"] == "PASS"

    def test_missing_invoice_number_returns_fail(self, client):
        response = client.post("/reviews", json=FAIL_INVOICE)
        assert response.status_code == 201
        assert response.json()["decision"] == "FAIL"

    def test_amount_exceeds_threshold_returns_needs_info(self, client):
        response = client.post("/reviews", json=NEEDS_INFO_INVOICE)
        assert response.status_code == 201
        assert response.json()["decision"] == "NEEDS_INFO"

    def test_response_contains_required_fields(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        body = response.json()
        assert "id"        in body
        assert "decision"  in body
        assert "reasons"   in body
        assert "evidence"  in body
        assert "timestamp" in body

    def test_response_id_is_integer(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        assert isinstance(response.json()["id"], int)

    def test_response_reasons_is_list(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        assert isinstance(response.json()["reasons"], list)

    def test_response_evidence_is_dict(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        assert isinstance(response.json()["evidence"], dict)

    def test_sequential_posts_get_incrementing_ids(self, client):
        r1 = client.post("/reviews", json=VALID_INVOICE)
        r2 = client.post("/reviews", json=VALID_INVOICE)
        assert r1.json()["id"] == 1
        assert r2.json()["id"] == 2

    def test_missing_total_amount_returns_needs_info(self, client):
        invoice = {**VALID_INVOICE, "total_amount": None}
        response = client.post("/reviews", json=invoice)
        assert response.json()["decision"] == "NEEDS_INFO"

    def test_missing_currency_returns_needs_info(self, client):
        invoice = {**VALID_INVOICE, "currency": None}
        response = client.post("/reviews", json=invoice)
        assert response.json()["decision"] == "NEEDS_INFO"

    def test_missing_vendor_name_returns_needs_info(self, client):
        invoice = {**VALID_INVOICE, "vendor_name": None}
        response = client.post("/reviews", json=invoice)
        assert response.json()["decision"] == "NEEDS_INFO"

    def test_unsupported_currency_returns_needs_info(self, client):
        invoice = {**VALID_INVOICE, "currency": "GBP"}
        response = client.post("/reviews", json=invoice)
        assert response.json()["decision"] == "NEEDS_INFO"

    def test_custom_threshold_via_rules_text(self, client):
        invoice = {**VALID_INVOICE, "total_amount": 1500.0, "rules_text": "max_amount=2000"}
        response = client.post("/reviews", json=invoice)
        assert response.json()["decision"] == "PASS"

    def test_evidence_contains_threshold(self, client):
        response = client.post("/reviews", json=VALID_INVOICE)
        assert "threshold" in response.json()["evidence"]

    def test_empty_body_still_returns_201(self, client):
        response = client.post("/reviews", json={})
        assert response.status_code == 201
        assert response.json()["decision"] == "FAIL"


# GET /reviews/{id}
class TestGetReviewById:

    def test_returns_200_for_existing_review(self, client):
        post = client.post("/reviews", json=VALID_INVOICE)
        review_id = post.json()["id"]
        response = client.get(f"/reviews/{review_id}")
        assert response.status_code == 200

    def test_returns_correct_decision(self, client):
        post = client.post("/reviews", json=VALID_INVOICE)
        review_id = post.json()["id"]
        response = client.get(f"/reviews/{review_id}")
        assert response.json()["decision"] == "PASS"

    def test_returns_404_for_missing_review(self, client):
        response = client.get("/reviews/99999")
        assert response.status_code == 404

    def test_404_response_has_detail_field(self, client):
        response = client.get("/reviews/99999")
        assert "detail" in response.json()

    def test_retrieved_review_matches_created_review(self, client):
        post = client.post("/reviews", json=NEEDS_INFO_INVOICE)
        post_body = post.json()
        review_id = post_body["id"]
        get_body = client.get(f"/reviews/{review_id}").json()
        assert get_body["id"]       == post_body["id"]
        assert get_body["decision"] == post_body["decision"]
        assert get_body["reasons"]  == post_body["reasons"]

    def test_get_review_contains_all_required_fields(self, client):
        post = client.post("/reviews", json=VALID_INVOICE)
        review_id = post.json()["id"]
        body = client.get(f"/reviews/{review_id}").json()
        assert "id"        in body
        assert "decision"  in body
        assert "reasons"   in body
        assert "evidence"  in body
        assert "timestamp" in body


# GET /reviews 
class TestListReviews:

    def test_returns_200(self, client):
        response = client.get("/reviews")
        assert response.status_code == 200

    def test_returns_empty_list_when_no_reviews(self, client):
        response = client.get("/reviews")
        assert response.json() == []

    def test_returns_list_after_reviews_created(self, client):
        client.post("/reviews", json=VALID_INVOICE)
        client.post("/reviews", json=FAIL_INVOICE)
        response = client.get("/reviews")
        assert len(response.json()) == 2

    def test_list_items_contain_required_fields(self, client):
        client.post("/reviews", json=VALID_INVOICE)
        items = client.get("/reviews").json()
        item = items[0]
        assert "id"        in item
        assert "decision"  in item
        assert "timestamp" in item

    def test_list_ordered_newest_first(self, client):
        client.post("/reviews", json=VALID_INVOICE)
        client.post("/reviews", json=NEEDS_INFO_INVOICE)
        items = client.get("/reviews").json()
        assert items[0]["id"] == 2
        assert items[1]["id"] == 1

    def test_list_reflects_correct_decisions(self, client):
        client.post("/reviews", json=VALID_INVOICE)
        client.post("/reviews", json=FAIL_INVOICE)
        items = client.get("/reviews").json()
        decisions = {item["id"]: item["decision"] for item in items}
        assert decisions[1] == "PASS"
        assert decisions[2] == "FAIL"