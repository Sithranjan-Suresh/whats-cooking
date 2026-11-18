"""Owner token / demo-mode actor resolution."""
import hmac
from typing import Literal, Optional

from fastapi import Header

from .config import get_settings
from .errors import AppError

Actor = Literal["owner", "demo"]


def resolve_actor(token: Optional[str]) -> Actor:
    s = get_settings()
    if token and s.owner_token and hmac.compare_digest(token, s.owner_token):
        return "owner"
    if token and s.owner_token:
        raise AppError("bad_owner_token", "That owner token is wrong.", 401)
    if s.demo_mode:
        return "demo"
    if not s.owner_token:
        # Local dev with no token configured: everyone is the owner.
        return "owner"
    raise AppError("unauthorized", "Owner token required.", 401)


def get_actor(x_owner_token: Optional[str] = Header(default=None)) -> Actor:
    return resolve_actor(x_owner_token)


def require_owner(actor: Actor) -> None:
    if actor != "owner":
        raise AppError("demo_mode", "This is disabled in demo mode. Unlock with the owner token in Settings.", 403)
