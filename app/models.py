import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from app.db import Base


class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id         = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Raw invoice input stored as serialized JSON string
    invoice_data = Column(Text, nullable=False)

    # Decision output
    decision = Column(String(20), nullable=False)
    reasons  = Column(Text, nullable=False)   # JSON serialized list
    evidence = Column(Text, nullable=False)   # JSON serialized dict

    # These properties let route handlers read reasons/evidence as Python objects
    # without manually calling json.loads every time.

    @property
    def reasons_list(self) -> list[str]:
        return json.loads(self.reasons)

    @property
    def evidence_dict(self) -> dict:
        return json.loads(self.evidence)

    @property
    def invoice_dict(self) -> dict:
        return json.loads(self.invoice_data)

    def __repr__(self) -> str:
        return f"<ReviewRequest id={self.id} decision={self.decision}>"