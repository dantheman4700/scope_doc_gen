"""Password hashing utilities using Argon2."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class PasswordService:
    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, plaintext: str) -> str:
        return self._hasher.hash(plaintext)

    def verify(self, hashed: str, plaintext: str) -> bool:
        try:
            return self._hasher.verify(hashed, plaintext)
        except VerifyMismatchError:
            return False

