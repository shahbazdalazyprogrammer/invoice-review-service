import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db
from app.schemas import (
    InvoiceReviewRequest,
    InvoiceReviewResponse,
    InvoiceReviewListItem,
)
from app.services.review_service import (
    create_review,
    get_review_by_id,
    get_all_reviews,
)

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/debug", tags=["Debug"])
def debug(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"db": "reachable"}
    except Exception as e:
        return {"db": "error", "detail": str(e)}

# Health Check
@router.get(
    "/health",
    tags=["Health"],
    summary="Service health check",
)
def health_check():
    """Returns service health status."""
    logger.info("Health check called.")
    return {"status": "ok"}


# Create Review 
@router.post(
    "/reviews",
    response_model=InvoiceReviewResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Reviews"],
    summary="Submit an invoice for review",
)
def post_review(
    invoice: InvoiceReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Accepts invoice data, applies deterministic rules,
    persists the result and returns the decision.

    Possible decisions:
    - **PASS** = all required fields present and within limits
    - **FAIL** = invoice_number is missing
    - **NEEDS_INFO** = one or more fields missing or amount exceeds threshold
    """
    try:
        result = create_review(invoice=invoice, db=db)
        return result
    except Exception as e:
        logger.exception("Unexpected error while creating review: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the invoice.",
        )


# Get Single Review
@router.get(
    "/reviews/{review_id}",
    response_model=InvoiceReviewResponse,
    status_code=status.HTTP_200_OK,
    tags=["Reviews"],
    summary="Fetch a review by ID",
)
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns the stored review record for the given ID,
    including the original decision, reasons, and evidence.
    """
    result = get_review_by_id(review_id=review_id, db=db)

    if result is None:
        logger.warning("Review not found | id=%s", review_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review with id {review_id} was not found.",
        )

    return result


# List All Reviews
@router.get(
    "/reviews",
    response_model=list[InvoiceReviewListItem],
    status_code=status.HTTP_200_OK,
    tags=["Reviews"],
    summary="List all review requests",
)
def list_reviews(
    db: Session = Depends(get_db),
):
    """
    Returns all stored reviews ordered by most recent first.
    Each item includes id, decision, and timestamp.
    """
    return get_all_reviews(db=db)