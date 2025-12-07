import logging
import os
import sys
import time
from typing import Any, Optional, Tuple

import pika
import pika.exceptions
import pika.exchange_type

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
# ...

logger = logging.getLogger(__name__)


class RabbitMQConnector:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        queue_name: str = "payment_events",
    ) -> None:
        self.host = host
        self.port = port
        self.queue_name = queue_name
        self.dlq_name = f"{queue_name}.dlq"

        self.username = os.getenv("RABBITMQ_USER", "poposing")
        self.password = os.getenv("RABBITMQ_PASS", "poposing1234")

        # [修正 3] 明確告訴 Mypy 這些變數一開始是 None，但未來會是物件
        # 我們用 Any 簡化 pika 複雜的型別
        self._connection: Optional[Any] = None
        self._channel: Optional[Any] = None

    def connect(self, retries: int = 5, delay: int = 2) -> Tuple[Any, Any]:
        while retries > 0:
            try:
                credentials = pika.PlainCredentials(self.username, self.password)

                self._connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=self.host,
                        port=self.port,
                        credentials=credentials,
                    )
                )
                self._channel = self._connection.channel()

                # [修正 2] 移除 assert，改用 Runtime Check
                # 這能同時滿足 Mypy (Type Guard) 和 Bandit (No assert)
                if self._channel is None:
                    raise RuntimeError("Failed to create RabbitMQ channel")

                # --- DLX 設定 ---
                dlx_name = "dlx_payment"
                self._channel.exchange_declare(
                    exchange=dlx_name,
                    exchange_type=pika.exchange_type.ExchangeType.direct,
                )
                self._channel.queue_declare(queue=self.dlq_name, durable=True)
                self._channel.queue_bind(
                    exchange=dlx_name, queue=self.dlq_name, routing_key="dead_letter"
                )

                arguments = {
                    "x-dead-letter-exchange": dlx_name,
                    "x-dead-letter-routing-key": "dead_letter",
                }
                self._channel.queue_declare(
                    queue=self.queue_name, durable=True, arguments=arguments
                )

                logger.info(
                    f"✅ Connected to RabbitMQ as {self.username}. DLQ configured."
                )

                # 這裡再次檢查 connection，滿足 Mypy
                if self._connection is None:
                    raise RuntimeError("Connection lost during setup")

                return self._connection, self._channel

            # [修正 4] 使用 pika.exceptions
            except pika.exceptions.AMQPConnectionError as e:
                logger.warning(f"⚠️ Connection failed ({e}). Retrying...")
                retries -= 1
                time.sleep(delay)
            except pika.exceptions.ProbableAuthenticationError:
                logger.error("❌ Authentication failed! Check your username/password.")
                sys.exit(1)

        logger.error("❌ Could not connect to RabbitMQ.")
        sys.exit(1)

    def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            self._connection.close()
