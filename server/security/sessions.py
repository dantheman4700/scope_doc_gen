"""Cookie-based session management using itsdangerous."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from itsdangerous import URLSafeSerializer, BadSignature

from server.core.config import SESSION_SECRET, SESSION_COOKIE_NAME


class SessionService:
    def __init__(self, *, secret: str = SESSION_SECRET, cookie_name: str = SESSION_COOKIE_NAME) -> None:
        self.serializer = URLSafeSerializer(secret_key=secret, salt="scope-session")
        self.cookie_name = cookie_name

    def create(self, user_id: str) -> str:
        payload = {
            "user_id": user_id,
            "issued_at": datetime.utcnow().isoformat(),
        }
        return self.serializer.dumps(payload)

    def parse(self, token: str) -> Optional[dict]:
        try:
            data = self.serializer.loads(token)
        except BadSignature:
            return None
        return data

