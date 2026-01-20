"""
Supabase database service - single source of truth for DB connection
"""

import os
from functools import lru_cache
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from dotenv import load_dotenv

load_dotenv()


@lru_cache()
def get_supabase() -> Client:
    """Get Supabase client (cached singleton) configured for kvota schema"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    # Use ClientOptions to set schema to kvota
    opts = ClientOptions(schema="kvota")
    return create_client(url, key, options=opts)


def get_anon_client() -> Client:
    """Get Supabase client with anon key (for auth) configured for kvota schema"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

    # Use ClientOptions to set schema to kvota
    opts = ClientOptions().replace(schema="kvota")
    return create_client(url, key, options=opts)
