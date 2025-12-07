import hashlib
import hmac
import logging
import os
from typing import Any, Dict

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# get from env
SECRET_KEY = os.getenv("SECRET_KEY", "my_suer_secret_key")  # noqa: S105


async def verify_signature(request: Request) -> bool:
    """
    Verify the signature (HMAC-SHA256)
    """

    # 1. header signature
    signature = request.headers.get("X-Signature")
    if not signature:
        logger.warning(" X-Signature header is missing")
        raise HTTPException(status_code=403, detail="X-Signature header is required")

    # 2. get body, 在FastAPI裡面body 讀去後要重置，不然後面會拿不到
    body_bytes = await request.body()

    async def receive() -> Dict[str, Any]:
        return {"type": "http.request", "body": body_bytes}

    request._receive = receive

    # 3. caculate HMAC
    expected_signature = hmac.new(
        SECRET_KEY.encode(), body_bytes, hashlib.sha256
    ).hexdigest()

    # 4. compare
    if not hmac.compare_digest(signature, expected_signature):
        logger.error(" X-Signature header is invalid")
        raise HTTPException(status_code=403, detail="X-Signature header is invalid")
    return True
