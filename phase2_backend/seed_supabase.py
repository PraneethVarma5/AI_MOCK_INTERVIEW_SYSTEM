"""
seed_supabase.py — Seeds HR and Role questions into Supabase.
Run ONCE after setting up your Supabase project.

Usage:
    pip install supabase python-dotenv
    python seed_supabase.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use SERVICE key (bypasses RLS)

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Import questions from your existing db_init.py ──────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))
from db_init import HR_QUESTIONS, ROLE_QUESTIONS

def seed_hr_questions():
    print("Seeding HR questions...")
    batch = []
    for text, qtype, diff in HR_QUESTIONS:
        batch.append({"text": text, "type": qtype, "difficulty": diff})

    # Upsert in batches of 50
    for i in range(0, len(batch), 50):
        chunk = batch[i:i+50]
        try:
            supabase.table("hr_questions").upsert(chunk, on_conflict="text").execute()
            print(f"  ✅ Inserted HR batch {i//50 + 1} ({len(chunk)} questions)")
        except Exception as e:
            print(f"  ❌ HR batch {i//50 + 1} failed: {e}")

def seed_role_questions():
    print("Seeding Role questions...")
    for role, questions in ROLE_QUESTIONS.items():
        batch = []
        for text, qtype, diff in questions:
            batch.append({"role": role, "text": text, "type": qtype, "difficulty": diff})

        try:
            supabase.table("role_questions").upsert(batch, on_conflict="role,text").execute()
            print(f"  ✅ {role}: {len(batch)} questions seeded")
        except Exception as e:
            print(f"  ❌ {role} failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Supabase seed...")
    seed_hr_questions()
    seed_role_questions()
    print("\n✅ Seeding complete!")
    
    # Verify counts
    hr_count = supabase.table("hr_questions").select("id", count="exact").execute()
    role_count = supabase.table("role_questions").select("id", count="exact").execute()
    print(f"   HR questions in DB: {hr_count.count}")
    print(f"   Role questions in DB: {role_count.count}")