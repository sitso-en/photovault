from decouple import config
from supabase import create_client

SUPABASE_URL = config("SUPABASE_URL")
SUPABASE_KEY = config("SUPABASE_KEY")
SUPABASE_BUCKET = config("SUPABASE_BUCKET")


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
