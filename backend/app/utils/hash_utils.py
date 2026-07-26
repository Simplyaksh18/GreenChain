import hashlib
import json
from typing import Any


def sha256_hash(data: Any) -> str:
    payload = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
