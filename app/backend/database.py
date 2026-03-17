from functools import lru_cache
from typing import Optional

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.backend.config import get_settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Returns a cached Supabase client using the anon key.
    Suitable for client-side operations that respect Row Level Security (RLS).
    """
    settings = get_settings()
    client: Client = create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_anon_key,
        options=ClientOptions(
            auto_refresh_token=True,
            persist_session=False,
        ),
    )
    return client


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """
    Returns a cached Supabase admin client using the service_role key.
    Bypasses Row Level Security (RLS) - use only for trusted server-side operations.
    """
    settings = get_settings()
    service_client: Client = create_client(
        supabase_url=settings.supabase_url,
        supabase_key=settings.supabase_service_role_key,
        options=ClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )
    return service_client


async def health_check() -> dict:
    """
    Performs a simple health check by pinging the Supabase instance.
    Returns a dict with 'status' and optional 'error' fields.
    """
    try:
        client = get_supabase_client()
        # Attempt a lightweight query to verify connectivity
        response = client.table("health_check").select("*").limit(1).execute()
        return {"status": "healthy", "detail": "Supabase connection is active"}
    except Exception as exc:
        return {"status": "unhealthy", "detail": str(exc)}


def reset_clients() -> None:
    """
    Clears the LRU caches for both clients.
    Useful for testing or when credentials change at runtime.
    """
    get_supabase_client.cache_clear()
    get_service_client.cache_clear()
