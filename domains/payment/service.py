import logging
import secrets
import time
from typing import Optional

import httpx
from sqlmodel import Session, select

from core.database import engine
from domains.payment.model import PaymentEvent

logger = logging.getLogger(__name__)


class PaymentService:
    def process_payment(
        self,
        order_id: str,
        amount: int,
        status: str,
        callback_url: Optional[str] = None,
    ) -> bool:
        """
        支付核心
        回傳： True , False (Retry, DLQ)
        """
        logger.info(f"🏦 [Service] Processing payment for {order_id}...")
        with Session(engine) as session:
            # 1. 檢查訂單是否已存在 (雖然 Redis 擋過，但 DB 是最後防線)
            existing_order = session.exec(
                select(PaymentEvent).where(PaymentEvent.order_id == order_id)
            ).first()

            if existing_order:
                logger.warning(f"⚠️ [Service] Order {order_id} already exists in DB.")
                return True  # 視為已處理，讓 Worker ACK

            # 2. 建立初始訂單 (狀態: PROCESSING)
            new_payment = PaymentEvent(
                order_id=order_id,
                amount=amount,
                status="PROCESSING",  # 初始狀態
            )
            session.add(new_payment)
            session.commit()
            session.refresh(new_payment)

            # 3. [模擬] 呼叫外部銀行 API (這裡是你的業務邏輯核心)
            # 實際上你會用 httpx 去打綠界/LinePay
            try:
                self._call_bank_api(order_id, amount)

                # 4. 銀行扣款成功 -> 更新狀態為 SUCCESS
                new_payment.status = "SUCCESS"
                session.add(new_payment)
                session.commit()
                logger.info(f"✅ [Service] Payment {order_id} SUCCESS.")

                if callback_url:
                    self._send_callback(callback_url, order_id, "SUCCESS")
                return True

            except Exception as e:
                # 5. 銀行扣款失敗 -> 更新狀態為 FAILED
                logger.error(f"❌ [Service] Bank error: {e}")
                new_payment.status = "FAILED"
                session.add(new_payment)
                session.commit()
                # 這裡要看你的策略：
                # 如果是「餘額不足」，那是業務失敗，回傳 True (不用重試)
                # 如果是「銀行斷線」，那是系統錯誤，回傳 False (需要 NACK 重試)

                if "Insufficient funds" in str(e):
                    return True
                if callback_url:
                    self._send_callback(callback_url, order_id, "FAILED")
                    raise e
                else:
                    raise e  # 拋出異常，讓 Worker 進行重試或 DLQ

    def _call_bank_api(self, order_id: str, amount: int) -> None:
        """模擬外部 API 呼叫"""
        time.sleep(0.5)  # 模擬網路延遲

        # 模擬隨機失敗
        if amount < 0:
            raise ValueError("Invalid Amount")

        # 模擬 10% 機率銀行斷線
        if secrets.randbits(8) < 26:
            raise ConnectionError("Bank API Timeout")  # nosec

        logger.info(f"💰 [Bank] Deducted {amount} for {order_id}")

    def _send_callback(self, url: str, order_id: str, status: str) -> None:
        """
        這就是你說的「主動回饋到呼應方」
        """
        logger.info(f" 📞 [Callback] Notifying {url} for {order_id} ({status})...")
        try:
            # 這裡簡單用 httpx 同步發送 (如果要高效能，這裡應該要再丟一個 task 進 Queue)
            response = httpx.post(
                url, json={"order_id": order_id, "status": status}, timeout=5.0
            )
            if response.status_code == 200:
                logger.info(" ✅ [Callback] Notification delivered.")
            else:
                logger.warning(
                    f" ⚠️ [Callback] Merchant responded {response.status_code}."
                )
        except Exception as e:
            logger.error(f" ❌ [Callback] Failed to notify: {e}")
            # 在真實系統中，這裡失敗應該要進「重試隊列 (Retry Queue)」
