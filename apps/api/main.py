import logging
from typing import Any, Dict, Generator

import pika
from fastapi import Depends, FastAPI, HTTPException
from opentelemetry.propagate import inject
from sqlmodel import Session, select

from core.cache import redis_client
from core.database import engine
from core.messaging import RabbitMQConnector
from core.security import verify_signature
from core.telemetry import instrument_app, setup_telemetry
from domains.payment.model import PaymentEvent
from domains.payment.schemas import WebhookPayload

setup_telemetry("flowpay-api")
app = FastAPI()

instrument_app(app, engine)


# Dependency Injection
def get_mq_channel() -> Generator[Any, None, None]:
    # 每次 Request 進來，實例化一個 Connector
    connector = RabbitMQConnector()
    connection, channel = connector.connect()
    try:
        yield channel
    finally:
        # Request 結束後，優雅關閉連線
        connector.close()


@app.post("/webhook", tags=["webhook"], dependencies=[Depends(verify_signature)])  # type: ignore
async def webhook(
    payload: WebhookPayload,
    channel: Any = Depends(get_mq_channel),  # noqa: B008
) -> Dict[str, str]:
    try:
        # 1. 序列化訊息
        message = payload.json()

        headers: Dict[str, Any] = {}
        inject(headers)
        properties = pika.BasicProperties(
            delivery_mode=2,
            headers=headers,
        )
        channel.basic_publish(
            exchange="",
            routing_key="payment_vents",
            body=message,
            properties=properties,
        )

        # 2. 丟進 Queue
        channel.basic_publish(
            exchange="",
            routing_key="payment_events",
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2  # 訊息持久化，RabbitMQ重啟不會消失
            ),
        )

        # logger
        logging.info(f" [x] Sent {message}")
        return {"status": "received"}
    except Exception as err:
        logging.error(f"Error: {err}")
        raise HTTPException(status_code=500, detail="Internal Server Error") from err


@app.get("/orders/{order_id}")  # type: ignore
async def get_order_status(order_id: str) -> Dict[str, str]:
    """
    讓使用者輪詢 (Poll) 訂單狀態
    """
    # 1. 先看 Redis 有沒有 Cache (減輕 DB 負擔)
    # 假設我們在 Worker 成功後有寫入 key: "order_status:{order_id}"
    # (你需要回去 Worker 補上這個邏輯，或者直接查 Redis 既有的 key)
    cached_status = redis_client.get(f"order_status:{order_id}")
    if cached_status:
        return {"order_id": order_id, "status": cached_status, "source": "redis"}

    # 2. Redis 沒有，才查 DB
    with Session(engine) as session:
        statement = select(PaymentEvent).where(PaymentEvent.order_id == order_id)
        order = session.exec(statement).first()

        if not order:
            # 可能是還在 Queue 裡排隊，還沒處理到
            # 或者是根本沒這筆單
            return {
                "order_id": order_id,
                "status": "PENDING_OR_NOT_FOUND",
                "source": "db",
            }

        return {"order_id": order_id, "status": order.status, "source": "db"}
