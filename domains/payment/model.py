from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


# 定義表結構
class PaymentEvent(SQLModel, table=True):
    # set table name
    __tablename__ = "payment_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: str = Field(index=True, unique=True)  # 加上 unique 索引防止重複
    amount: int
    status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
