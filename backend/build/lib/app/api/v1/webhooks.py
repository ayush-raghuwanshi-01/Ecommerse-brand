from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import payment_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
Db = Annotated[Session, Depends(get_db)]


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Db,
    signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
):
    raw = await request.body()
    result = payment_service.process_webhook(db, raw, signature or "")
    db.commit()
    return result
