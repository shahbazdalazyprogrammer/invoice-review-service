import json
import logging
import time
from sqlalchemy.orm import Session

from app.models import ReviewRequest
from app.schemas import InvoiceReviewRequest, InvoiceReviewResponse, InvoiceReviewListItem
from app.services.decision import evaluate_invoice

logger = logging.getLogger(__name__)


def create_review(
    invoice: InvoiceReviewRequest,
    db: Session,
) -> InvoiceReviewResponse:
    """
    Runs the decision logic on the invoice, persists the result,
    and returns a structured response.
    """
    start = time.perf_counter()

    logger.info(
        "Review request received | invoice_number=%s vendor=%s amount=%s",
        invoice.invoice_number,
        invoice.vendor_name,
        invoice.total_amount,
    )

    # Run decision logic
    decision, reasons, evidence = evaluate_invoice(invoice)

    # Persist to database
    try:
        record = ReviewRequest(
            invoice_data = json.dumps(invoice.model_dump()),
            decision     = decision,
            reasons      = json.dumps(reasons),
            evidence     = json.dumps(evidence),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except Exception as db_error:
        db.rollback()
        logger.exception("Database error while saving review: %s", db_error)
        raise
    
    # Log outcome
    elapsed = (time.perf_counter() - start) * 1000  # convert to ms
    logger.info(
        "Review completed | id=%s decision=%s reasons=%s processing_time=%.2fms",
        record.id,
        record.decision,
        reasons,
        elapsed,
    )

    # Return response
    return InvoiceReviewResponse(
        id        = record.id,
        decision  = record.decision,
        reasons   = record.reasons_list,
        evidence  = record.evidence_dict,
        timestamp = record.created_at,
    )


def get_review_by_id(
    review_id: int,
    db: Session,
) -> InvoiceReviewResponse | None:
    """
    Fetches a single review by primary key.
    Returns None if not found then the route decides the HTTP response.
    """
    record = db.query(ReviewRequest).filter(ReviewRequest.id == review_id).first()

    if not record:
        logger.warning("Review not found | id=%s", review_id)
        return None

    return InvoiceReviewResponse(
        id        = record.id,
        decision  = record.decision,
        reasons   = record.reasons_list,
        evidence  = record.evidence_dict,
        timestamp = record.created_at,
    )


def get_all_reviews(
    db: Session,
    limit: int = 100,
) -> list[InvoiceReviewListItem]:
    """
    Returns all reviews ordered by most recent first.
    Used 'limit' rows to avoid unbounded queries.
    """
    records = (
        db.query(ReviewRequest)
        .order_by(ReviewRequest.created_at.desc())
        .limit(limit)
        .all()
    )

    logger.info("Listing reviews | count=%s", len(records))

    return [
        InvoiceReviewListItem(
            id        = r.id,
            decision  = r.decision,
            timestamp = r.created_at,
        )
        for r in records
    ]