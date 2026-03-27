# -*- coding: utf-8 -*-
"""Database module, including the Supabase database object and DB-related utilities."""

from supabase import create_client
from app.settings import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)