"""Authentication provider abstractions."""

from .base import AuthError, AuthUnsupportedError, AuthProvider, SessionUser
from .local import LocalAuthProvider
from .supabase import SupabaseAuthProvider

__all__ = [
    "AuthError",
    "AuthUnsupportedError",
    "AuthProvider",
    "SessionUser",
    "LocalAuthProvider",
    "SupabaseAuthProvider",
]

