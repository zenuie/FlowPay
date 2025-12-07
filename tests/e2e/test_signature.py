import hashlib
import hmac

SECRET = "my_suer_secret_key"  # noqa: S105  # 跟你 core/security.py 裡預設的一樣


def calculate_signature(body_bytes: bytes) -> str:
    return hmac.new(SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()
