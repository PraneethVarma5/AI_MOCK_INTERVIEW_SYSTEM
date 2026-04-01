from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import sys
import os
import shutil
import hashlib
import json
import sqlite3
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


# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load .env from current dir and parent dir
load_dotenv()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=False)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"), override=False)

DB_PATH = os.path.join(os.path.dirname(__file__), "interview.db")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "question_cache.json")


# ── DATABASE HELPER ───────────────────────────────────────────────────────────
def get_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=500,
            detail="Database not found. Please run: python db_init.py"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── CACHE HELPERS ─────────────────────────────────────────────────────────────
def get_cache_key(resume_text, num_questions, difficulty, job_description, auto_select_count):
    content = f"{resume_text[:5000]}|{num_questions}|{difficulty}|{job_description[:3000]}|{auto_select_count}"
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


# ── RESUME PARSER IMPORT ──────────────────────────────────────────────────────
from resume_parser import parse_resume

# ── PYDANTIC MODELS ───────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    resume_text: str
    job_description: str = ""
    difficulty: str = "mixed"
    num_questions: int = 5
    auto_select_count: bool = False
    force_refresh: bool = False

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
    mode: Optional[str] = "resume"  # resume | hr | role


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
        # Add your deployed frontend URL later, e.g.
        # "https://your-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Initialize globally
if QuestionGenerator is not None:
    try:
        question_generator = QuestionGenerator()
    except Exception as e:
        print(f"Warning: Failed to initialize QuestionGenerator: {e}")
        question_generator = None
else:
    question_generator = None
    
try:
    answer_evaluator = AnswerEvaluator()
except Exception as e:
    print(f"Warning: Failed to initialize AnswerEvaluator: {e}")
    answer_evaluator = None


# ── BASIC ROUTES ──────────────────────────────────────────────────────────────
@app.get("/")
def read_root():
    return {"message": "AI Mock Interview Backend is Running"}

@app.get("/health")
def health_check():
    gemini_present = bool(
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or
        os.getenv("RECRUITER_API_KEYS") or os.getenv("GEMINI_API_KEYS")
    )
    db_ok = os.path.exists(DB_PATH)
    return {
        "status": "ok",
        "question_generator_ready": question_generator is not None,
        "answer_evaluator_ready": answer_evaluator is not None,
        "gemini_key_detected": gemini_present,
        "database_ready": db_ok
    }


# ── DATABASE ROUTES ───────────────────────────────────────────────────────────
@app.get("/db/roles")
def get_available_roles():
    """Return all roles that have questions in the database."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT role FROM role_questions ORDER BY role")
        roles = [row["role"] for row in cur.fetchall()]
        conn.close()
        return {"roles": roles}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/db/hr_questions")
def get_hr_questions(num_questions: int = 5, difficulty: str = "mixed"):
    """Fetch HR/behavioral questions from the database with fallback top-up if a difficulty bucket is short."""
    num_questions = max(1, min(num_questions, 20))

    try:
        conn = get_db()
        cur = conn.cursor()

        rows = []

        if difficulty == "mixed":
            cur.execute(
                "SELECT * FROM hr_questions ORDER BY RANDOM() LIMIT ?",
                (num_questions,)
            )
            rows = cur.fetchall()
        else:
            # First try exact difficulty
            cur.execute(
                "SELECT * FROM hr_questions WHERE difficulty = ? ORDER BY RANDOM() LIMIT ?",
                (difficulty, num_questions)
            )
            primary_rows = cur.fetchall()
            rows.extend(primary_rows)

            # Top up from other difficulties if needed
            remaining = num_questions - len(primary_rows)
            if remaining > 0:
                cur.execute(
                    """
                    SELECT * FROM hr_questions
                    WHERE difficulty != ?
                    AND id NOT IN ({})
                    ORDER BY RANDOM()
                    LIMIT ?
                    """.format(",".join("?" for _ in primary_rows) if primary_rows else "0"),
                    ([difficulty] + [row["id"] for row in primary_rows] + [remaining]) if primary_rows
                    else [difficulty, remaining]
                )
                fallback_rows = cur.fetchall()
                rows.extend(fallback_rows)

        conn.close()

        questions = []
        for idx, row in enumerate(rows[:num_questions], start=1):
            questions.append({
                "id": idx,
                "text": row["text"],
                "type": row["type"],
                "difficulty": row["difficulty"],
                "context": "[HR] Behavioral competency question",
                "initial_code": ""
            })

        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/db/role_questions")
def get_role_questions(role: str, num_questions: int = 5, difficulty: str = "mixed"):
    """Fetch role-specific questions from the database with fallback top-up if a difficulty bucket is short."""
    num_questions = max(1, min(num_questions, 20))

    try:
        conn = get_db()
        cur = conn.cursor()

        rows = []

        if difficulty == "mixed":
            cur.execute(
                "SELECT * FROM role_questions WHERE role = ? ORDER BY RANDOM() LIMIT ?",
                (role, num_questions)
            )
            rows = cur.fetchall()
        else:
            # First try exact difficulty
            cur.execute(
                "SELECT * FROM role_questions WHERE role = ? AND difficulty = ? ORDER BY RANDOM() LIMIT ?",
                (role, difficulty, num_questions)
            )
            primary_rows = cur.fetchall()
            rows.extend(primary_rows)

            # Top up from other difficulties for same role
            remaining = num_questions - len(primary_rows)
            if remaining > 0:
                cur.execute(
                    """
                    SELECT * FROM role_questions
                    WHERE role = ?
                    AND difficulty != ?
                    AND id NOT IN ({})
                    ORDER BY RANDOM()
                    LIMIT ?
                    """.format(",".join("?" for _ in primary_rows) if primary_rows else "0"),
                    ([role, difficulty] + [row["id"] for row in primary_rows] + [remaining]) if primary_rows
                    else [role, difficulty, remaining]
                )
                fallback_rows = cur.fetchall()
                rows.extend(fallback_rows)

        conn.close()

        questions = []
        for idx, row in enumerate(rows[:num_questions], start=1):
            questions.append({
                "id": idx,
                "text": row["text"],
                "type": row["type"],
                "difficulty": row["difficulty"],
                "context": f"[Role] {role} core competency",
                "initial_code": ""
            })

        if not questions:
            raise HTTPException(
                status_code=404,
                detail=f"No questions found for role '{role}'. Check available roles at /db/roles"
            )

        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── BATCH EVALUATE ROUTE ──────────────────────────────────────────────────────
@app.post("/batch_evaluate")
def batch_evaluate_answers(request: BatchEvaluateRequest):
    """
    HR / Role -> always local hybrid evaluation (0 Gemini calls)
    Resume    -> Gemini batch evaluation first, local hybrid fallback if Gemini fails
    """
    try:
        if answer_evaluator is None:
            raise HTTPException(status_code=500, detail="Answer evaluator not initialized")

        mode = (request.mode or "resume").lower()

        if mode in ["hr", "role"]:
            results = answer_evaluator.evaluate_local_batch(request.answers)
        else:
            # Resume mode: batch_evaluate already contains Gemini -> local fallback
            results = answer_evaluator.batch_evaluate(request.answers)

        return {"results": results}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Batch evaluation failed: {e}")

        # Final safety net: NEVER let frontend receive hard failure
        try:
            fallback_results = answer_evaluator.evaluate_local_batch(request.answers)
            return {"results": fallback_results}
        except Exception as inner_e:
            print(f"Final local fallback also failed: {inner_e}")
            raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")
                
# ── RESUME UPLOAD ─────────────────────────────────────────────────────────────
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
        print(f"\n--- EXTRACTED RESUME TEXT (FIRST 300 CHARS) ---\n{safe_text}\n---\n")

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
    No manual/default job role.
    Gemini infers the likely role from resume skills/projects/experience and optional JD.
    """
    try:
        if not request.resume_text or not request.resume_text.strip():
            raise HTTPException(status_code=400, detail="Resume text is required.")

        # Clamp question count for safety
        request.num_questions = max(3, min(request.num_questions, 20))

        # Cache key WITHOUT role
        cache_key = get_cache_key(
            request.resume_text,
            request.num_questions,
            request.difficulty,
            request.job_description,
            request.auto_select_count
        )

        # Use cache unless force refresh
        if not request.force_refresh:
            cache = read_cache()
            if cache_key in cache:
                cached_questions = cache[cache_key]
                return {"questions": cached_questions}

        # If Gemini generator is unavailable, use generic fallback (no role)
        if question_generator is None:
            fallback = get_fallback_questions(
                request.resume_text,
                num_questions=request.num_questions
            )
            return {"questions": fallback}

        # Gemini decides role internally from resume/JD
        questions = question_generator.generate_questions(
            resume_text=request.resume_text,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            job_description=request.job_description,
            auto_select_count=request.auto_select_count
        )

        if not questions or len(questions) == 0:
            fallback = get_fallback_questions(
                request.resume_text,
                num_questions=request.num_questions
            )
            return {"questions": fallback}

        # Cache successful result
        cache = read_cache()
        cache[cache_key] = questions
        write_cache(cache)

        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Question generation error: {e}")

        # Safe generic fallback (no role)
        fallback = get_fallback_questions(
            request.resume_text,
            num_questions=request.num_questions
        )
        return {"questions": fallback}

# ── LEGACY SINGLE EVALUATE (kept for backward compat) ────────────────────────
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
            "feedback": f"Evaluation service unavailable. Error: {str(e)[:120]}...",
            "missing_keywords": [],
            "improvements": "Check API connection or add GEMINI_API_KEY in .env",
            "ideal_answer": "AI evaluation fallback triggered.",
            "ml_relevance_score": None,
            "ml_relevance_grade": None,
            "hybrid_score": 0
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)