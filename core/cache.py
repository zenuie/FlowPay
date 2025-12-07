import sys

import redis
from redis import Redis

# 這裡應該要讀環境變數，現在先寫死，為了讓你趕快跑起來
REDIS_URL = "redis://localhost:6379/0"


def get_redis_client() -> Redis[str]:
    try:
        # decode_responses=True 讓拿出來的資料直接是字串，不用 decode bytes
        client = redis.from_url(REDIS_URL, decode_responses=True)
        # Ping 一下確保連線成功
        if client.ping():
            return client
        raise redis.ConnectionError("Ping failed")
    except redis.ConnectionError as e:
        print(f"❌ Redis connection failed: {e}")
        sys.exit(1)


# 建立一個單例物件供大家使用
redis_client: Redis[str] = get_redis_client()
