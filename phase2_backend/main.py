"""
main.py — InterviewAI Backend (Supabase edition)
Replaces all SQLite usage with Supabase.
Adds: auth middleware, experience level support, session persistence.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
import sys
import os
import shutil
import hashlib
import json
import time
from typing import List, Optional
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from question_bank import get_fallback_questions
from evaluator import AnswerEvaluator
import tempfile

try:
    from question_generator import QuestionGenerator
except Exception as e:
    print(f"Warning: Could not import QuestionGenerator: {e}")
    QuestionGenerator = None

import uvicorn

# Force UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()
_dir = os.path.dirname(__file__)
load_dotenv(dotenv_path=os.path.join(_dir, ".env"), override=False)
load_dotenv(dotenv_path=os.path.join(_dir, "..", ".env"), override=False)

CACHE_FILE = os.path.join(_dir, "question_cache.json")

# ── SUPABASE ──────────────────────────────────────────────────────────────────
from supabase_client import get_supabase_admin

# ── CACHE HELPERS ─────────────────────────────────────────────────────────────
def get_cache_key(resume_text, num_questions, difficulty, job_description, auto_select_count, experience_level="experienced", experience_years=""):
    content = f"{resume_text[:5000]}|{num_questions}|{difficulty}|{job_description[:3000]}|{auto_select_count}|{experience_level}|{experience_years}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def read_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def write_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

# ── RESUME PARSER ──────────────────────────────────────────────────────────────
from resume_parser import parse_resume

# ── AUTH HELPER ───────────────────────────────────────────────────────────────
def get_user_id_from_request(request: Request) -> Optional[str]:
    """Extract Supabase user ID from Authorization header. Returns None for guests."""
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    if not token:
        return None
    try:
        from supabase_client import get_supabase
        sb = get_supabase()
        user = sb.auth.get_user(token)
        return str(user.user.id) if user and user.user else None
    except Exception:
        return None

# ── PYDANTIC MODELS ───────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    resume_text: str
    job_description: str = ""
    difficulty: str = "mixed"
    num_questions: int = 5
    auto_select_count: bool = False
    force_refresh: bool = False
    experience_level: str = "experienced"   # "fresher" | "experienced"
    experience_years: str = ""              # "1", "2", "3-5", "5+" (only if experienced)

class QuestionModel(BaseModel):
    id: int
    text: str
    type: str
    difficulty: str
    context: str
    initial_code: str = ""

class QuestionResponse(BaseModel):
    questions: List[QuestionModel]

class AnswerItem(BaseModel):
    question: str
    answer: str
    type: Optional[str] = "technical"
    difficulty: Optional[str] = "medium"
    keywords: Optional[List[str]] = None
    ideal_answer: Optional[str] = None

class BatchEvaluateRequest(BaseModel):
    answers: List[AnswerItem]
    mode: Optional[str] = "resume"
    session_id: Optional[str] = None  # For saving results to Supabase

class SaveSessionRequest(BaseModel):
    session_id: str
    overall_score: float
    results: List[dict]


# ── APP SETUP ─────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Mock Interview API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "https://ai-mock-interview-system-project.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount auth and analytics routers ──────────────────────────────────────────
from auth import router as auth_router
from analytics import router as analytics_router
app.include_router(auth_router)
app.include_router(analytics_router)

# ── Initialize evaluator and generator ────────────────────────────────────────
if QuestionGenerator is not None:
    try:
        question_generator = QuestionGenerator()
    except Exception as e:
        print(f"Warning: QuestionGenerator init failed: {e}")
        question_generator = None
else:
    question_generator = None

try:
    answer_evaluator = AnswerEvaluator()
except Exception as e:
    print(f"Warning: AnswerEvaluator init failed: {e}")
    answer_evaluator = None


# ── BASIC ROUTES ──────────────────────────────────────────────────────────────
@app.get("/")
def read_root():
    return {"message": "AI Mock Interview Backend is Running (Supabase edition)"}

@app.get("/health")
def health_check():
    gemini_present = bool(
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or
        os.getenv("RECRUITER_API_KEYS") or os.getenv("GEMINI_API_KEYS")
    )
    supabase_ok = bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))
    return {
        "status": "ok",
        "question_generator_ready": question_generator is not None,
        "answer_evaluator_ready": answer_evaluator is not None,
        "gemini_key_detected": gemini_present,
        "supabase_connected": supabase_ok
    }


# ── DATABASE ROUTES (now Supabase) ────────────────────────────────────────────
@app.get("/db/roles")
def get_available_roles():
    try:
        sb = get_supabase_admin()
        res = sb.table("role_questions").select("role").execute()
        roles = sorted(list(set(r["role"] for r in (res.data or []))))
        return {"roles": roles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/db/hr_questions")
def get_hr_questions(num_questions: int = 5, difficulty: str = "mixed"):
    num_questions = max(1, min(num_questions, 20))
    try:
        sb = get_supabase_admin()
        query = sb.table("hr_questions").select("*")
        if difficulty != "mixed":
            query = query.eq("difficulty", difficulty)
        res = query.limit(num_questions * 3).execute()
        rows = res.data or []

        # Shuffle and pick
        import random
        random.shuffle(rows)
        rows = rows[:num_questions]

        questions = []
        for idx, row in enumerate(rows, start=1):
            questions.append({
                "id": idx,
                "text": row["text"],
                "type": row["type"],
                "difficulty": row["difficulty"],
                "context": "[HR] Behavioral competency question",
                "initial_code": ""
            })

        # Top-up with other difficulties if needed
        if len(questions) < num_questions and difficulty != "mixed":
            remaining = num_questions - len(questions)
            existing_ids = [r["id"] for r in rows]
            res2 = sb.table("hr_questions").select("*") \
                .not_.in_("id", existing_ids) \
                .limit(remaining).execute()
            for row in (res2.data or []):
                questions.append({
                    "id": len(questions) + 1,
                    "text": row["text"],
                    "type": row["type"],
                    "difficulty": row["difficulty"],
                    "context": "[HR] Behavioral competency question",
                    "initial_code": ""
                })

        return {"questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/db/role_questions")
def get_role_questions(role: str, num_questions: int = 5, difficulty: str = "mixed"):
    num_questions = max(1, min(num_questions, 20))
    try:
        sb = get_supabase_admin()
        query = sb.table("role_questions").select("*").eq("role", role)
        if difficulty != "mixed":
            query = query.eq("difficulty", difficulty)
        res = query.limit(num_questions * 3).execute()
        rows = res.data or []

        if not rows:
            raise HTTPException(status_code=404, detail=f"No questions found for role '{role}'")

        import random
        random.shuffle(rows)
        rows = rows[:num_questions]

        questions = []
        for idx, row in enumerate(rows, start=1):
            questions.append({
                "id": idx,
                "text": row["text"],
                "type": row["type"],
                "difficulty": row["difficulty"],
                "context": f"[Role] {role} core competency",
                "initial_code": ""
            })

        return {"questions": questions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── SESSION MANAGEMENT ────────────────────────────────────────────────────────
@app.post("/sessions/create")
async def create_session(request: Request, data: dict):
    """Create a new interview session and return session_id."""
    user_id = get_user_id_from_request(request)
    sb = get_supabase_admin()
    try:
        session_data = {
            "user_id": user_id,
            "mode": data.get("mode", "resume"),
            "role": data.get("role"),
            "difficulty": data.get("difficulty", "mixed"),
            "experience_level": data.get("experience_level", "experienced"),
            "experience_years": data.get("experience_years", ""),
            "num_questions": data.get("num_questions", 5),
            "status": "in_progress"
        }
        res = sb.table("sessions").insert(session_data).execute()
        session = res.data[0] if res.data else {}
        return {"session_id": session.get("id"), "session": session}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str, request: Request, data: dict):
    """Save evaluation results and mark session as completed."""
    user_id = get_user_id_from_request(request)
    sb = get_supabase_admin()
    try:
        results = data.get("results", [])
        overall_score = data.get("overall_score", 0)
        questions = data.get("questions", [])

        # Save each answer
        answers_to_insert = []
        for i, result in enumerate(results):
            q = questions[i] if i < len(questions) else {}
            answers_to_insert.append({
                "session_id": session_id,
                "question_index": i,
                "question_text": q.get("text", result.get("question", "")),
                "question_type": q.get("type", "technical"),
                "question_difficulty": q.get("difficulty", "medium"),
                "user_answer": result.get("answer", ""),
                "score": result.get("score"),
                "feedback": result.get("feedback", ""),
                "improvements": result.get("improvements", ""),
                "ideal_answer": result.get("ideal_answer", ""),
                "missing_keywords": result.get("missing_keywords", [])
            })

        if answers_to_insert:
            sb.table("session_answers").insert(answers_to_insert).execute()

        # Update session
        
        sb.table("sessions").update({
        "overall_score": overall_score,
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", session_id).execute()

        return {"message": "Session saved successfully", "session_id": session_id}
    except Exception as e:
        print(f"Session save error: {e}")
        # Don't fail the user — saving is best-effort
        return {"message": "Session partially saved", "error": str(e)}


@app.get("/sessions/history")
async def get_session_history(request: Request, limit: int = 20):
    """Get session history for the current user."""
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    sb = get_supabase_admin()
    try:
        res = sb.table("sessions") \
            .select("id, mode, role, difficulty, overall_score, created_at, status, num_questions") \
            .eq("user_id", user_id) \
            .eq("status", "completed") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return {"sessions": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── BATCH EVALUATE ────────────────────────────────────────────────────────────
@app.post("/batch_evaluate")
async def batch_evaluate_answers(request: Request, req: BatchEvaluateRequest):
    try:
        if answer_evaluator is None:
            raise HTTPException(status_code=500, detail="Answer evaluator not initialized")

        mode = (req.mode or "resume").lower()

        if mode in ["hr", "role"]:
            results = answer_evaluator.evaluate_local_batch(req.answers)
        else:
            results = answer_evaluator.batch_evaluate(req.answers)

        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Batch evaluation failed: {e}")
        try:
            fallback_results = answer_evaluator.evaluate_local_batch(req.answers)
            return {"results": fallback_results}
        except Exception as inner_e:
            raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ── RESUME UPLOAD ──────────────────────────────────────────────────────────────
@app.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...), job_role: str = Form("")):
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".tmp"
    fd, temp_file = tempfile.mkstemp(prefix="resume_", suffix=suffix)
    os.close(fd)
    try:
        with open(temp_file, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        data = parse_resume(temp_file, job_role=job_role)
        safe_text = data.text[:300].encode("utf-8", "replace").decode("utf-8")
        print(f"\n--- RESUME TEXT (FIRST 300) ---\n{safe_text}\n---\n")

        return {
            "filename": file.filename,
            "extracted_text": data.text,
            "message": "Resume processed successfully",
            "skill_match": getattr(data, "skill_match", {})
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)


# ── QUESTION GENERATION (Resume+JD mode) ─────────────────────────────────────
@app.post("/generate_questions", response_model=QuestionResponse)
def generate_questions(request: QuestionRequest):
    """
    Resume + optional JD mode.
    Now supports experience_level (fresher/experienced) and experience_years.
    """
    try:
        if not request.resume_text or not request.resume_text.strip():
            raise HTTPException(status_code=400, detail="Resume text is required.")

        request.num_questions = max(3, min(request.num_questions, 20))

        cache_key = get_cache_key(
            request.resume_text,
            request.num_questions,
            request.difficulty,
            request.job_description,
            request.auto_select_count,
            request.experience_level,
            request.experience_years
        )

        if not request.force_refresh:
            cache = read_cache()
            if cache_key in cache:
                return {"questions": cache[cache_key]}

        if question_generator is None:
            fallback = get_fallback_questions(request.resume_text, num_questions=request.num_questions)
            return {"questions": fallback}

        # Build experience context for the prompt
        exp_context = _build_experience_context(request.experience_level, request.experience_years)

        questions = question_generator.generate_questions(
            resume_text=request.resume_text,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            job_description=request.job_description,
            auto_select_count=request.auto_select_count,
            experience_context=exp_context
        )

        if not questions:
            fallback = get_fallback_questions(request.resume_text, num_questions=request.num_questions)
            return {"questions": fallback}

        cache = read_cache()
        cache[cache_key] = questions
        write_cache(cache)

        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Question generation error: {e}")
        fallback = get_fallback_questions(request.resume_text, num_questions=request.num_questions)
        return {"questions": fallback}


def _build_experience_context(experience_level: str, experience_years: str) -> str:
    """Build experience context string to inject into the question generation prompt."""
    if experience_level == "fresher":
        return (
            "CANDIDATE EXPERIENCE LEVEL: FRESHER (0-1 years or student/recent graduate).\n"
            "IMPORTANT: Generate questions appropriate for a fresher. Focus on:\n"
            "- Academic projects and personal/hobby projects\n"
            "- Conceptual understanding and fundamentals\n"
            "- Learning agility and theoretical knowledge\n"
            "- DO NOT ask about 'years of experience', 'production systems', or senior-level scenarios.\n"
            "- Frame behavioral questions around college/academic experiences.\n"
        )
    elif experience_level == "experienced":
        years_str = f"{experience_years} years" if experience_years else "multiple years"
        return (
            f"CANDIDATE EXPERIENCE LEVEL: EXPERIENCED ({years_str} of professional experience).\n"
            "IMPORTANT: Generate questions appropriate for an experienced professional. Focus on:\n"
            "- Real-world project experience and production systems\n"
            "- Technical depth, architecture decisions, and trade-offs\n"
            "- Leadership, mentoring, and cross-team collaboration\n"
            "- Performance, scalability, and engineering best practices.\n"
        )
    return ""


# ── LEGACY SINGLE EVALUATE ────────────────────────────────────────────────────
@app.post("/evaluate_answer")
def evaluate_answer(data: dict):
    question = (data.get("question") or "").strip()
    answer = data.get("answer", "")
    if not question:
        raise HTTPException(status_code=400, detail="Missing question")
    if answer is None:
        answer = ""
    try:
        if not answer_evaluator:
            raise Exception("AnswerEvaluator not initialized")
        result = answer_evaluator.evaluate(question, answer)
        return {
            "score": result.score,
            "feedback": result.feedback,
            "missing_keywords": result.missing_keywords,
            "improvements": result.improvements,
            "ideal_answer": result.ideal_answer,
            "ml_relevance_score": getattr(result, "ml_relevance_score", None),
            "ml_relevance_grade": getattr(result, "ml_relevance_grade", None),
            "hybrid_score": getattr(result, "hybrid_score", None)
        }
    except Exception as e:
        print(f"Evaluation Error: {e}")
        return {
            "score": 0,
            "feedback": f"Evaluation service unavailable: {str(e)[:120]}",
            "missing_keywords": [],
            "improvements": "Check API connection or add GEMINI_API_KEY in .env",
            "ideal_answer": "AI evaluation fallback triggered.",
            "ml_relevance_score": None,
            "ml_relevance_grade": None,
            "hybrid_score": 0
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)