import asyncio
import json
import logging
import time
import uuid

import httpx

from tests.e2e.test_signature import calculate_signature

API_URL = "http://localhost:8000/webhook"
CONCURRENCY_LEVEL = 500  # 同時發射 50 發

logging.getLogger("httpx").setLevel(logging.WARNING)


async def send_order(client: httpx.AsyncClient, index: int) -> bool:
    """
    發送單筆訂單的任務 (Task)
    """
    order_id = f"STRESS_{uuid.uuid4()}"[:20]  # 縮短一點比較好看
    payload = {
        "order_id": order_id,
        "amount": 100 + index,  # 為了區分，金額不一樣
        "status": "STRESS_TEST",
    }
    content = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    sig = calculate_signature(content)
    headers = {"X-Signature": sig, "Content-Type": "application/json"}

    try:
        start_time = time.time()
        # 這裡發出請求，但不會卡住等待，Event Loop 會切去處理別的請求
        resp = await client.post(API_URL, content=content, headers=headers)
        duration = time.time() - start_time

        if resp.status_code == 200:
            print(f"✅ [Req {index}] Success ({duration:.2f}s) - {order_id}")

            return True
        else:
            print(f"❌ [Req {index}] Failed ({resp.status_code})")
            return False

    except Exception as e:
        print(f"💥 [Req {index}] Error: {e}")
        return False


async def test_stress_concurrency() -> None:
    print(f"🚀 Starting Stress Test with {CONCURRENCY_LEVEL} concurrent requests...")
    start_total = time.time()

    # 使用 AsyncClient 的 Context Manager，這很重要！
    # 它會建立 Connection Pool (連線池)，復用 TCP 連線，效能才會高。
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []

        # 1. 建立任務清單 (只是建立，還沒開始跑)
        for i in range(CONCURRENCY_LEVEL):
            # 注意：這裡沒有 await！我們只是把 coroutine 物件放進 list
            tasks.append(send_order(client, i))

        print("🔥 FIRE!")

        # 2. 此時此刻，萬箭齊發！
        # asyncio.gather 會同時啟動所有 tasks，並等待它們全部做完
        results = await asyncio.gather(*tasks)

    end_total = time.time()
    total_time = end_total - start_total
    success_count = sum(1 for r in results if r)

    print("-" * 40)
    print("📊 Report:")
    print(f"   Total Requests: {CONCURRENCY_LEVEL}")
    print(f"   Success:        {success_count}")
    print(f"   Failed:         {CONCURRENCY_LEVEL - success_count}")
    print(f"   Total Time:     {total_time:.2f}s")
    # 計算 TPS (Transactions Per Second)
    print(f"   TPS (Approx):   {CONCURRENCY_LEVEL / total_time:.2f} req/s")
    print("-" * 40)
