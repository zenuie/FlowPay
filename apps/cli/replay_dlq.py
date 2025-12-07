import logging

# 確保 python path 抓得到 core
import os
import sys

sys.path.insert(0, os.getcwd())

from core.messaging import RabbitMQConnector  # noqa: E402

# 設定 Log
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def replay() -> None:
    connector = RabbitMQConnector()
    try:
        connection, channel = connector.connect()
    except Exception as e:
        logger.error(f"Cannot connect to RabbitMQ: {e}")
        return

    dlq_name = connector.dlq_name  # payment_events.dlq
    main_queue = connector.queue_name  # payment_events

    # 檢查 DLQ 有多少訊息
    queue_state = channel.queue_declare(queue=dlq_name, durable=True, passive=True)
    message_count = queue_state.method.message_count

    if message_count == 0:
        logger.info(" ✅ DLQ is empty. Nothing to replay.")
        connector.close()
        return

    logger.info(f" ♻️ Found {message_count} messages in {dlq_name}. Starting replay...")

    replayed_count = 0

    # 這裡我們用 basic_get 一筆一筆抓，比較安全
    while True:
        method, properties, body = channel.basic_get(queue=dlq_name)

        if method is None:
            break

        try:
            # 1. 重新發送到主 Queue
            if properties.headers:
                properties.headers.pop("x-death", None)
                properties.headers.pop("x-first-death-exchange", None)
                properties.headers.pop("x-first-death-queue", None)
                properties.headers.pop("x-first-death-reason", None)

            channel.basic_publish(
                exchange="", routing_key=main_queue, body=body, properties=properties
            )

            # 2. 只有發送成功後，才刪除 DLQ 裡的舊資料 (ACK)
            channel.basic_ack(delivery_tag=method.delivery_tag)
            replayed_count += 1
            print(
                f"\r 🔄 Replayed: {replayed_count}/{message_count}",
                end="",
                flush=True,  # noqa: E501
            )

        except Exception as e:
            logger.error(f" ❌ Error replaying message: {e}")
            # 如果發送失敗，就不要 ACK，讓它留在 DLQ
            break

    print("\n")
    logger.info(f" 🎉 Successfully replayed {replayed_count} messages.")
    connector.close()


if __name__ == "__main__":
    replay()
