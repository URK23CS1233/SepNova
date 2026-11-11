from contextvars import ContextVar
from fastapi import Request
from supabase import create_client, Client
from .config import get_settings
from functools import lru_cache
from typing import Any

_demo_ctx: ContextVar[bool] = ContextVar("demo_mode", default=False)


@lru_cache()
def get_supabase() -> Client:
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_key)


def set_demo_mode(value: bool):
    return _demo_ctx.set(value)


def reset_demo_mode(token):
    _demo_ctx.reset(token)


def is_demo_mode() -> bool:
    return _demo_ctx.get()


def get_db(request: Request = None) -> Any:
    """Return a demo in-memory DB for demo requests (Bearer demo), else real Supabase."""
    try:
        demo = _demo_ctx.get()
        if not demo and request is not None:
            auth = request.headers.get("authorization", "") or ""
            demo = auth.strip().lower() == "bearer demo"
        if demo:
            from .demo_db import get_demo_db
            return get_demo_db()
    except Exception:
        pass
    return get_supabase()
