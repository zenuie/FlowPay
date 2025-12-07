from typing import Optional

from pydantic import BaseModel


class WebhookPayload(BaseModel):
    order_id: str
    amount: int
    status: str
    callback_url: Optional[str] = None
