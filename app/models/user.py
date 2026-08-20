"""User model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: int | None
    full_name: str
    email: str
    password_hash: str
    role: str
    department: str | None
    status: str
    created_at: str | None = None
