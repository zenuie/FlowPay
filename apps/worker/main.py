# apss/worker/main.py
import json
import logging
import signal
from datetime import timedelta
from typing import Any

from core.cache import redis_client
from core.messaging import RabbitMQConnector
from domains.payment.service import PaymentService

# 實例化 Service (Singleton)
payment_service = PaymentService()


def process_message(ch: Any, method: Any, properties: Any, body: bytes) -> None:
    try:
        data = json.loads(body)
        order_id = data.get("order_id")
        lock_key = f"processed:{order_id}"

        # 如果 key 不存在 -> 寫入成功，回傳 True -> 代表我是第一個，繼續執行
        # 如果 key 已存在 -> 寫入失敗，回傳 None -> 代表有人搶先了，直接 ACK
        is_first = redis_client.set(lock_key, "1", nx=True, ex=timedelta(hours=24))

        if not is_first:
            logging.info(f" ♻️ [Redis] Order {order_id} locked/processed. Skipping.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # [核心] 呼叫業務邏輯層
        # Worker 不應該知道 DB 怎麼連，也不應該知道怎麼扣款
        # 它只管 Service 執行成不成功
        success = payment_service.process_payment(
            order_id=order_id,
            amount=data.get("amount"),
            status=data.get("status"),
            callback_url=data.get("callback_url"),
        )

        # 業務邏輯成功 (包含扣款成功 或 扣款失敗但已紀錄)
        if success:
            # [防線 2] 寫入 Redis 標記已處理
            ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        logging.error(f" ❌ System Error: {e}")
        # 決定重試策略：
        # 如果是 ConnectionError，也許可以 NACK requeue=True (這需要更細的判斷)
        # 這裡我們先統一進 DLQ
        logging.warning(" 💀 Moving message to DLQ...")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# -------------------------------------------------------------


# 全域變數，控制是否繼續執行
should_run = True


def signal_handler(sig: int, frame: Any) -> None:
    global should_run
    logging.warning(
        f" 🛑 Received shutdown signal ({sig}). Stopping worker gracefully..."
    )
    should_run = False
    # 注意：這裡不能直接 channel.stop_consuming()，因為可能會有執行緒問題
    # 我們透過 flag 控制


def main() -> None:
    connector = RabbitMQConnector()
    connection, channel = connector.connect()
    channel.basic_qos(prefetch_count=1)

    # 註冊信號監聽
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Docker stop

    logging.info(" [*] Worker started. Press CTRL+C to exit.")

    # 使用 generator 或是手動迴圈來消費，這樣才能控制停止
    # 注意：pika 的 start_consuming 是阻塞的，要做到 Graceful Shutdown
    # 最好改用 consume generator

    for method, properties, body in channel.consume(
        queue=connector.queue_name, inactivity_timeout=1
    ):
        if not should_run:
            break

        if method is None:
            # timeout，沒訊息，繼續迴圈檢查 should_run
            continue

        # 呼叫你的處理邏輯
        process_message(channel, method, properties, body)

    # 迴圈結束，開始清理資源
    logging.info(" 🧹 Closing connections...")
    try:
        if channel.is_open:
            channel.cancel()  # 告訴 MQ 我不收了
        connector.close()
    except Exception:
        logging.info(" 🧹 Connection already closed.")
    logging.info(" 👋 Bye.")


if __name__ == "__main__":
    main()
