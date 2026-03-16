# Invoice Review Service

A minimal, production-ready backend service for rule-based invoice review.

Submits invoice data via REST API, applies deterministic business rules,
and returns a structured decision: `PASS`, `FAIL`, or `NEEDS_INFO`.
---

## Architecture Overview
```
invoice-review-service/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, router registration
│   ├── db.py                    # Database engine, session, get_db dependency
│   ├── models.py                # SQLAlchemy ORM model (review_requests table)
│   ├── schemas.py               # Pydantic request/response models
│   ├── api/
│   │   └── routes_reviews.py   # HTTP route handlers
│   └── services/
│       ├── decision.py          # Pure decision logic: no I/O
│       └── review_service.py   # DB persistence and service orchestration
└── tests/
    ├── conftest.py              # Pytest fixtures and test DB setup
    ├── test_decision.py         # Unit tests for decision logic
    └── test_api.py              # API integration tests
```

### Layer responsibilities

| Layer | Files | Responsibility |
|---|---|---|
| HTTP | `routes_reviews.py` | Parse requests, call services, return responses |
| Service | `review_service.py` | Orchestrate logic + DB, logging, timing |
| Logic | `decision.py` | Pure deterministic rules, no side effects |
| Persistence | `models.py`, `db.py` | ORM model, session management |
| Schema | `schemas.py` | Request/response contracts |
---

## Chosen Stack

| Component | Choice
|---|---|
| Framework | FastAPI
| Language | Python 3.11
| ORM | SQLAlchemy 2.0 |
| DB (local) | SQLite |
| DB (prod) | PostgreSQL |
| Server | Uvicorn | 
| Testing | Pytest + HTTPX |
---

## API Endpoints

### `GET /health`
Returns service health status.
```bash
curl https://x.onrender.com/health
```
```json
{"status": "ok"}
```
---

### `POST /reviews`
Submits an invoice for review. Applies deterministic rules and returns a decision.
```bash
curl -X POST https://x.onrender.com/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_number": "INV-123",
    "vendor_name": "Acme GmbH",
    "total_amount": 500.0,
    "currency": "EUR",
    "invoice_date": "2026-01-15",
    "customer_name": "Beta Corp",
    "due_date": "2026-03-30"
  }'
```
```json
{
  "id": 1,
  "decision": "PASS",
  "reasons": ["All required fields are present and values are within limits."],
  "evidence": {
    "invoice_number_present": true,
    "vendor_name_present": true,
    "total_amount": 500.0,
    "currency": "EUR",
    "threshold": 1000.0
  },
  "timestamp": "2026-03-15T13:45:00Z"
}
```

**Optional field:** `rules_text`: override the default amount threshold.  
Example: `"rules_text": "max_amount=5000"` sets the threshold to 5000.

---

### `GET /reviews/{id}`
Fetches a stored review by ID.
```bash
curl https://x.onrender.com/reviews/1
```

Returns `404` if the ID does not exist.

---

### `GET /reviews`
Lists all stored reviews, ordered by most recent first.
```bash
curl https://x.onrender.com/reviews
```
```json
[
  {"id": 2, "decision": "FAIL", "timestamp": "2026-03-15T14:00:00Z"},
  {"id": 1, "decision": "PASS", "timestamp": "2026-03-15T13:45:00Z"}
]
```

---

## Rule Logic

Rules are applied in priority order. All matching rules are collected
before a final decision is issued. `FAIL` always beats `NEEDS_INFO`,
which always beats `PASS`.

| # | Condition | Decision |
|---|---|---|
| 1 | `invoice_number` is missing or empty | `FAIL` |
| 2 | `total_amount` is missing | `NEEDS_INFO` |
| 3 | `currency` is missing | `NEEDS_INFO` |
| 4 | `vendor_name` is missing | `NEEDS_INFO` |
| 5 | `currency` not in `EUR`, `USD` | `NEEDS_INFO` |
| 6 | `total_amount` exceeds threshold (default 1000) | `NEEDS_INFO` |
| 7 | All checks pass | `PASS` |

**Priority system:** `FAIL (2) > NEEDS_INFO (1) > PASS (0)`  
Multiple rules can fire simultaneously: all reasons are collected
and the highest-priority decision wins.

**Threshold override:** If `rules_text` contains `max_amount=N`,
that value replaces the default threshold of 1000. The threshold
used is always included in the `evidence` field.

---

## Running Locally
```bash
# Clone the repo
git clone https://github.com/x/invoice-review-service
cd invoice-review-service

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  

# Install dependencies
pip install -r requirements.txt

# Rename the .env_example folder to .env and set these values
set DATABASE_URL=sqlite:///./app.db
set AMOUNT_THRESHOLD=1000.0

# Run the server
uvicorn app.main:app --reload
```

## Running Tests
```bash
pytest tests/ -v
```

| File | Type
|---|---|
| `tests/test_decision.py` | Unit tests |
| `tests/test_api.py` | Integration tests 

Tests use an isolated file-based SQLite database (`test.db`) that is
created before each test and dropped afterward. The real `app.db` is
never touched during testing.
```bash

## Deployment

Deployed on **Render** as a Python web service.

**Environment variables set in Render dashboard:**

| Variable | Value |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (Connection values from Render) |
| `AMOUNT_THRESHOLD` | `1000.0` |

**Start command:**
```
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## What I Would Improve Next

| Improvement | Reason |
|---|---|
| PostgreSQL native JSONB columns | Better querying and indexing on `reasons` and `evidence` |
| Pagination on `GET /reviews` | Unbounded queries will slow down at scale |
| API key authentication | Protect the service from unauthorized access |
| More flexible rule engine | Allow rules to be configured per-client, not just via `rules_text` |
| Docker + docker-compose | Reproducible local environment with PostgreSQL |
| CI/CD pipeline | Run tests automatically on every push via GitHub Actions |
| Structured JSON logging | Machine-readable logs for log aggregation tools |