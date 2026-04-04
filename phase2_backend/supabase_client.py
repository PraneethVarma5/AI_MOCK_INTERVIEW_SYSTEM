# supabase_client.py
import os
from functools import lru_cache
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

@lru_cache()
def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
    return create_client(url, anon)

@lru_cache()
def get_supabase_admin() -> Client:
    url = os.getenv("SUPABASE_URL")
    service = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not service:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(url, service)