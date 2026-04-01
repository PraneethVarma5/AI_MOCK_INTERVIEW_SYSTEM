from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import re
from dotenv import load_dotenv

# Load .env
# Load .env from current working dir, backend folder, and parent project root
load_dotenv()
_current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(_current_dir, ".env"), override=False)
load_dotenv(dotenv_path=os.path.join(_current_dir, "..", ".env"), override=False)


class EvaluationResult(BaseModel):
    score: float
    feedback: str
    missing_keywords: List[str]
    improvements: str = ""
    ideal_answer: str = ""
    ml_relevance_score: Optional[float] = None
    ml_relevance_grade: Optional[str] = None
    hybrid_score: Optional[float] = None


# Optional ML helper
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


def calculate_tfidf_score(user_answer: str, ideal_answer: str) -> dict:
    """Local TF-IDF scoring — zero API calls."""
    try:
        if not ML_AVAILABLE:
            return {"relevance_score": 50.0, "grade": "N/A"}

        if not user_answer or not ideal_answer or len(user_answer.strip()) < 5:
            return {"relevance_score": 0.0, "grade": "Needs Improvement"}

        vectorizer = TfidfVectorizer(stop_words='english', min_df=1)
        vectors = vectorizer.fit_transform([user_answer, ideal_answer])
        similarity = cosine_similarity(vectors[0], vectors[1])[0][0]
        relevance = round(float(similarity) * 100, 1)

        if relevance >= 80:
            grade = "Excellent"
        elif relevance >= 60:
            grade = "Good"
        elif relevance >= 40:
            grade = "Fair"
        else:
            grade = "Needs Improvement"

        return {"relevance_score": relevance, "grade": grade}
    except Exception as e:
        print(f"TF-IDF error: {e}")
        return {"relevance_score": 50.0, "grade": "N/A"}


def _hybrid_score(gemini_score: float, tfidf_relevance: float) -> float:
    """70% Gemini AI score + 30% TF-IDF semantic similarity."""
    tfidf_normalized = (tfidf_relevance / 100) * 10
    return round((gemini_score * 0.7) + (tfidf_normalized * 0.3), 1)


class AnswerEvaluator:
    def __init__(self):
        self.stopwords = {
            "what", "why", "how", "when", "where", "which", "who", "whom",
            "would", "could", "should", "tell", "about", "your", "with", "from",
            "that", "this", "have", "been", "into", "through", "they", "them",
            "their", "role", "position", "project", "experience", "explain",
            "describe", "walk", "start", "look", "give", "using", "used",
            "specifically", "interested", "great", "think", "before", "after",
            "wrap", "around", "please", "difference", "between", "example",
            "would", "approach", "would", "handle", "there", "then", "than",
            "also", "just", "more", "most", "into", "over", "under"
        }

        # Tiny synonym map for better keyword matching
        self.synonyms = {
            "api": ["rest api", "endpoint", "service", "http api"],
            "database": ["db", "sql", "nosql", "table", "query"],
            "testing": ["unit test", "integration test", "test cases", "test"],
            "performance": ["optimize", "latency", "speed", "throughput"],
            "scalability": ["scale", "scalable"],
            "debugging": ["debug", "troubleshoot", "investigate bug"],
            "authentication": ["auth", "login", "identity"],
            "authorization": ["access control", "permissions", "roles"],
            "react": ["jsx", "component", "hooks"],
            "python": ["pandas", "flask", "django"],
            "javascript": ["js", "node", "frontend"],
            "machine learning": ["ml", "model", "training", "prediction"],
            "data analysis": ["eda", "analysis", "insights", "dataset"],
            "leadership": ["led", "owned", "guided", "managed"],
            "teamwork": ["collaborated", "worked with", "team", "cross-functional"],
            "conflict": ["disagreement", "resolved", "handled issue"],
        }
        self.behavioral_templates = {
            "ask_for_help": {
                "triggers": ["ask for help", "needed help", "sought help", "complete something important"],
                "keywords": ["deadline", "challenge", "asked for help", "collaboration", "solution", "result", "learning"],
                "ideal": "A strong answer should explain the important task, why help was needed, who you approached, how you communicated clearly, what changed after getting support, and the final successful outcome."
            },
            "repetitive_work": {
                "triggers": ["repetitive work", "maintaining accuracy", "repetitive task", "attention to detail"],
                "keywords": ["accuracy", "process", "checklist", "consistency", "focus", "quality", "result"],
                "ideal": "A strong answer should explain the repetitive task, the system or process you used to avoid mistakes, how you maintained consistency, and the final outcome or quality result."
            },
            "motivation_difficult": {
                "triggers": ["motivated yourself", "difficult period", "stay motivated", "challenging time"],
                "keywords": ["challenge", "motivation", "discipline", "routine", "small goals", "consistency", "result"],
                "ideal": "A strong answer should explain the difficult period, what caused the drop in motivation, the specific actions you took to stay disciplined, and the positive outcome or lesson learned."
            },
            "why_new_opportunity": {
                "triggers": ["why are you looking for a new opportunity", "why new opportunity", "why change jobs", "why now"],
                "keywords": ["growth", "learning", "new challenge", "career goals", "impact", "alignment"],
                "ideal": "A strong answer should frame the move positively, focus on growth, learning, greater impact, and explain how the new opportunity aligns with long-term goals."
            },
            "ideal_work_environment": {
                "triggers": ["ideal work environment", "work environment", "best environment"],
                "keywords": ["collaboration", "communication", "support", "feedback", "growth", "accountability", "respect"],
                "ideal": "A strong answer should describe a collaborative, respectful, growth-oriented environment with clear communication, constructive feedback, accountability, and alignment with performance."
            },
            "team_conflict": {
                "triggers": ["disagreed with a teammate", "conflict with teammate", "team conflict", "disagreement"],
                "keywords": ["communication", "understanding", "resolution", "respect", "collaboration", "result"],
                "ideal": "A strong answer should explain the disagreement calmly, how you listened and communicated, what compromise or resolution happened, and how the relationship or project improved."
            },
            "strengths": {
                "triggers": ["greatest strength", "your strengths", "biggest strength"],
                "keywords": ["strength", "example", "impact", "evidence", "result"],
                "ideal": "A strong answer should name one real strength, support it with a specific example, and show how it creates value in a professional setting."
            },
            "weakness": {
                "triggers": ["greatest weakness", "your weakness", "biggest weakness"],
                "keywords": ["weakness", "self-awareness", "improvement", "action", "progress"],
                "ideal": "A strong answer should name a genuine but manageable weakness, explain what you are doing to improve it, and show measurable progress."
            }
        }

    # -------------------------------------------------------------------------
    # BASIC HELPERS
    # -------------------------------------------------------------------------
    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()
    
    def _detect_behavioral_template(self, question: str) -> Optional[Dict[str, Any]]:
        q = self._normalize(question)

        for template in self.behavioral_templates.values():
            for trigger in template["triggers"]:
                if self._normalize(trigger) in q:
                    return template

        return None

    def _extract_keywords_from_question(self, question: str, q_type: str = "technical") -> List[str]:
        """
        Better fallback keyword extraction.
        For behavioral questions, prefer category-based templates instead of dumb word scraping.
        """
        q_type = (q_type or "technical").lower()

        # Behavioral: use template-based keywords first
        if q_type == "behavioral":
            template = self._detect_behavioral_template(question)
            if template:
                return template["keywords"]

            # Generic behavioral fallback (safe, not trash)
            return ["situation", "action", "result", "example", "lesson", "outcome"]

        # Technical / coding fallback
        text = self._normalize(question)
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-\+\.#]*", text)
        words = [w for w in words if len(w) > 2 and w not in self.stopwords]

        seen = set()
        keywords = []
        for w in words:
            if w not in seen:
                seen.add(w)
                keywords.append(w)

        defaults = ["example", "approach"]
        for kw in defaults:
            if kw not in keywords:
                keywords.append(kw)

        return keywords[:8]

    def _generate_ideal_answer(self, question: str, q_type: str = "technical") -> str:
        q_type = (q_type or "technical").lower()

        if q_type == "behavioral":
            template = self._detect_behavioral_template(question)
            if template:
                return template["ideal"]

            return (
                "A strong behavioral answer should follow the STAR method: explain the situation, "
                "your task, the action you took, and the measurable result."
            )

        elif q_type == "coding":
            return (
                "A strong coding answer should explain the approach clearly, write correct logic, "
                "consider edge cases, and mention time or space complexity when relevant."
            )

        return (
            "A strong technical answer should define the concept clearly, explain the core trade-offs, "
            "and give at least one practical example or real-world use case."
        )
    def _keyword_match(self, answer: str, keywords: List[str]) -> Dict[str, Any]:
        """
        Flexible keyword matching:
        - direct phrase match
        - singular/plural-ish tolerance
        - synonym match
        """
        answer_norm = self._normalize(answer)
        matched = []
        missing = []

        for kw in keywords:
            kw_norm = self._normalize(kw)
            found = False

            # direct
            if kw_norm and kw_norm in answer_norm:
                found = True

            # very light stem-ish fallback
            if not found:
                kw_base = kw_norm.rstrip("s")
                if kw_base and kw_base in answer_norm:
                    found = True

            # synonyms
            if not found:
                for base, syns in self.synonyms.items():
                    if kw_norm == base or kw_norm in syns:
                        for alt in [base] + syns:
                            if self._normalize(alt) in answer_norm:
                                found = True
                                break
                    if found:
                        break

            if found:
                matched.append(kw)
            else:
                missing.append(kw)

        total = max(len(keywords), 1)
        coverage = len(matched) / total

        # 0-10 score
        if coverage == 0:
            keyword_score = 0.0
        elif coverage < 0.25:
            keyword_score = 2.0
        elif coverage < 0.50:
            keyword_score = 4.0
        elif coverage < 0.70:
            keyword_score = 6.0
        elif coverage < 0.90:
            keyword_score = 8.0
        else:
            keyword_score = 9.5

        return {
            "matched": matched,
            "missing": missing,
            "coverage": coverage,
            "keyword_score": keyword_score
        }

    def _semantic_score(self, answer: str, ideal_answer: str) -> Dict[str, Any]:
        tfidf = calculate_tfidf_score(answer, ideal_answer)
        rel = tfidf["relevance_score"]

        # Convert 0-100 relevance to 0-10 semantic score
        if rel >= 85:
            semantic_score = 9.5
        elif rel >= 70:
            semantic_score = 8.0
        elif rel >= 55:
            semantic_score = 6.5
        elif rel >= 40:
            semantic_score = 5.0
        elif rel >= 25:
            semantic_score = 3.5
        else:
            semantic_score = 1.5 if answer.strip() else 0.0

        return {
            "semantic_score": semantic_score,
            "relevance_score": tfidf["relevance_score"],
            "grade": tfidf["grade"]
        }

    def _structure_bonus(self, answer: str, q_type: str) -> float:
        """
        Small sanity bonus only. No stupid length worship.
        Max 1.0
        """
        ans = self._normalize(answer)
        if not ans:
            return 0.0

        words = ans.split()
        bonus = 0.0

        if len(words) >= 8:
            bonus += 0.3
        if len(words) >= 20:
            bonus += 0.2

        if q_type.lower() == "behavioral":
            # Soft STAR-ish clues
            star_clues = [
                "when", "during", "in my project", "situation",
                "i decided", "i handled", "i solved", "i led",
                "result", "finally", "we achieved", "outcome"
            ]
            matches = sum(1 for clue in star_clues if clue in ans)
            if matches >= 2:
                bonus += 0.3
            if matches >= 4:
                bonus += 0.2

        elif q_type.lower() in ["technical", "coding"]:
            tech_clues = [
                "because", "for example", "for instance", "approach",
                "complexity", "edge case", "trade-off", "first", "then"
            ]
            matches = sum(1 for clue in tech_clues if clue in ans)
            if matches >= 2:
                bonus += 0.3
            if matches >= 4:
                bonus += 0.2

        return round(min(bonus, 1.0), 2)

    def _build_feedback(self, final_score: float, q_type: str, coverage: float) -> str:
        if final_score >= 8:
            return "Strong answer. It covers the key points, stays relevant to the question, and shows decent structure."
        elif final_score >= 6:
            return "Decent answer, but it needs stronger coverage of the core points and a clearer example or explanation."
        elif final_score >= 4:
            return "Partially correct, but the answer misses important ideas. Cover the main concepts more directly and structure it better."
        else:
            if q_type.lower() == "behavioral":
                return "The answer is too vague or incomplete. Use a clear STAR-style example with your actions and the result."
            return "The answer misses key concepts from the question. Be more direct, explain the core idea clearly, and include one practical example."

    def _build_improvement(self, q_type: str, missing_keywords: List[str]) -> str:
        base = {
            "behavioral": "Use a STAR structure: situation, action, and measurable result.",
            "coding": "Explain the logic clearly, mention edge cases, and include time or space complexity if relevant.",
            "technical": "Define the concept clearly, cover trade-offs, and give one practical example."
        }.get((q_type or "technical").lower(), "Answer more directly and cover the key points clearly.")

        if missing_keywords:
            return f"{base} Also cover: {', '.join(missing_keywords[:4])}."
        return base

    def _evaluate_one_local(self, item: Any) -> Dict[str, Any]:
        """
        Local hybrid evaluator for ANY mode.
        Supports optional metadata:
        - item.keywords
        - item.ideal_answer
        """
        q = item.question if hasattr(item, 'question') else item.get('question', '')
        a = item.answer if hasattr(item, 'answer') else item.get('answer', '')
        q_type = item.type if hasattr(item, 'type') else item.get('type', 'technical')
        q_diff = item.difficulty if hasattr(item, 'difficulty') else item.get('difficulty', 'medium')

        # Optional metadata (future-proof)
        item_keywords = item.keywords if hasattr(item, 'keywords') and getattr(item, 'keywords', None) is not None else item.get('keywords', None) if isinstance(item, dict) else None
        item_ideal = item.ideal_answer if hasattr(item, 'ideal_answer') and getattr(item, 'ideal_answer', None) is not None else item.get('ideal_answer', None) if isinstance(item, dict) else None

        answer = (a or "").strip()

        keywords = item_keywords if item_keywords else self._extract_keywords_from_question(q, q_type)
        ideal = item_ideal if item_ideal else self._generate_ideal_answer(q, q_type)

        if not answer:
            return {
                "question": q,
                "answer": "",
                "type": q_type,
                "difficulty": q_diff,
                "score": 0.0,
                "feedback": "No answer provided. Try answering even briefly so the system can assess relevance and structure.",
                "missing_keywords": keywords[:5],
                "improvements": self._build_improvement(q_type, keywords[:4]),
                "ideal_answer": ideal,
                "ml_relevance_score": 0.0,
                "ml_relevance_grade": "Needs Improvement",
                "hybrid_score": 0.0
            }

        keyword_data = self._keyword_match(answer, keywords)
        semantic_data = self._semantic_score(answer, ideal)
        structure_bonus = self._structure_bonus(answer, q_type)

        # FINAL HYBRID
        # 60% keyword + 30% semantic + structure bonus (0-1)
        if q_type.lower() == "behavioral":
            # Behavioral should rely more on structure + semantic meaning,
            # less on literal keyword matching
            final_score = round(
                min(
                    (keyword_data["keyword_score"] * 0.35) +
                    (semantic_data["semantic_score"] * 0.45) +
                    (structure_bonus * 2.0),   # structure becomes up to 2 pts
                    10.0
                ),
                1
            )
        else:
            # Technical / coding
            final_score = round(
                min(
                    (keyword_data["keyword_score"] * 0.6) +
                    (semantic_data["semantic_score"] * 0.3) +
                    structure_bonus,
                    10.0
                ),
                1
            )
        feedback = self._build_feedback(final_score, q_type, keyword_data["coverage"])
        improvements = self._build_improvement(q_type, keyword_data["missing"])

        return {
            "question": q,
            "answer": answer,
            "type": q_type,
            "difficulty": q_diff,
            "score": final_score,
            "feedback": feedback,
            "missing_keywords": keyword_data["missing"][:5],
            "improvements": improvements,
            "ideal_answer": ideal,
            "ml_relevance_score": semantic_data["relevance_score"],
            "ml_relevance_grade": semantic_data["grade"],
            "hybrid_score": final_score
        }

    # -------------------------------------------------------------------------
    # LOCAL BATCH EVALUATION (HR / ROLE + Resume fallback)
    # -------------------------------------------------------------------------
    def evaluate_local_batch(self, answers: list) -> list:
        """
        Main local hybrid evaluator.
        Use this for:
        - HR mode
        - Role mode
        - Resume mode fallback when Gemini fails
        """
        results = []
        for item in answers:
            results.append(self._evaluate_one_local(item))
        return results

    # -------------------------------------------------------------------------
    # GEMINI BATCH EVALUATE (Resume primary)
    # -------------------------------------------------------------------------
    def batch_evaluate(self, answers: list) -> list:
        """
        Resume mode primary:
        Sends ALL Q&A pairs to Gemini in ONE prompt.
        If Gemini fails, FALLS BACK to local hybrid evaluation.
        """
        from ai_utils import run_genai_with_rotation

        qa_lines = []
        for i, item in enumerate(answers, start=1):
            q = item.question if hasattr(item, 'question') else item.get('question', '')
            a = item.answer if hasattr(item, 'answer') else item.get('answer', '')
            is_skipped = not a or a.strip() == ""
            if not is_skipped and len(a) > 1200:
                a = a[:1200] + " ...[truncated]"
            answer_text = "NO ANSWER PROVIDED. CANDIDATE SKIPPED." if is_skipped else a

            # Optional metadata if present
            item_keywords = item.keywords if hasattr(item, 'keywords') and getattr(item, 'keywords', None) is not None else item.get('keywords', None) if isinstance(item, dict) else None
            item_ideal = item.ideal_answer if hasattr(item, 'ideal_answer') and getattr(item, 'ideal_answer', None) is not None else item.get('ideal_answer', None) if isinstance(item, dict) else None

            meta_block = ""
            if item_keywords:
                meta_block += f"\nExpected keywords{i}: {item_keywords}"
            if item_ideal:
                meta_block += f"\nReference ideal answer{i}: {item_ideal}"

            qa_lines.append(f"""
Q{i}: {q}
A{i}: {answer_text}{meta_block}""")

        qa_block = "\n".join(qa_lines)
        n = len(answers)

        prompt = f"""You are a senior technical interviewer evaluating a mock interview session.
Evaluate ALL {n} question-answer pairs below and return a JSON array of {n} evaluation objects.

INTERVIEW TRANSCRIPT:
{qa_block}

EVALUATION INSTRUCTIONS:
- Score each answer from 0–10 (0 if skipped/blank).
- Be fair but critical. Strong answers score 7–9. Perfect answers 10.
- Keep ideal_answer to MAX 2–3 sentences — direct and concise.
- For skipped answers: score=0, create a model ideal_answer anyway.
- If reference keywords or a reference ideal answer are provided for a question, use them as guidance.

RETURN ONLY a JSON array with exactly {n} objects, each with:
{{
  "score": int (0-10),
  "feedback": "1-2 sentence evaluation",
  "missing_keywords": ["keyword1", "keyword2"],
  "improvements": "1 short sentence",
  "ideal_answer": "1-2 sentence model answer"
}}

Return ONLY the raw JSON array. No markdown, no explanation."""

        try:
            print(f"Batch evaluating {n} answers in 1 Gemini call...")
            response_text = run_genai_with_rotation(prompt, is_json=True)

            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)

            if isinstance(data, dict):
                data = data.get("evaluations") or data.get("results") or list(data.values())[0]

            if not isinstance(data, list):
                raise ValueError(f"Expected JSON array, got {type(data)}")

            results = []
            for i, item in enumerate(answers):
                q = item.question if hasattr(item, 'question') else item.get('question', '')
                a = item.answer if hasattr(item, 'answer') else item.get('answer', '')
                q_type = item.type if hasattr(item, 'type') else item.get('type', 'technical')
                q_diff = item.difficulty if hasattr(item, 'difficulty') else item.get('difficulty', 'medium')

                eval_data = data[i] if i < len(data) else {}
                gemini_score = float(eval_data.get("score", 0))
                ideal = eval_data.get("ideal_answer", "")

                tfidf = calculate_tfidf_score(a, ideal)
                h_score = _hybrid_score(gemini_score, tfidf["relevance_score"])

                results.append({
                    "question": q,
                    "answer": a,
                    "type": q_type,
                    "difficulty": q_diff,
                    "score": h_score,
                    "feedback": eval_data.get("feedback", "No feedback."),
                    "missing_keywords": eval_data.get("missing_keywords", []),
                    "improvements": eval_data.get("improvements", ""),
                    "ideal_answer": ideal,
                    "ml_relevance_score": tfidf["relevance_score"],
                    "ml_relevance_grade": tfidf["grade"],
                    "hybrid_score": h_score
                })

            return results

        except Exception as e:
            print(f"Batch evaluation failed: {e}. Falling back to local hybrid evaluation.")
            return self.evaluate_local_batch(answers)

    # -------------------------------------------------------------------------
    # SINGLE EVALUATE (legacy endpoint)
    # -------------------------------------------------------------------------
    def evaluate(self, question: str, answer: str, context_keywords: List[str] = []) -> EvaluationResult:
        """
        Legacy single evaluation endpoint.
        Tries Gemini first, falls back to local hybrid evaluation.
        """
        from ai_utils import run_genai_with_rotation

        is_skipped = not answer or answer.strip() == "" or "no answer provided" in answer.lower()

        prompt = f"""You are an expert technical interviewer evaluating a candidate's response.

QUESTION: "{question}"
CANDIDATE ANSWER: "{'NO ANSWER PROVIDED. CANDIDATE SKIPPED.' if is_skipped else answer}"

OBJECTIVES:
1. Score the answer from 0-10. {'(MUST BE 0 since candidate skipped)' if is_skipped else '(Be fair and critical)'}
2. Provide helpful feedback (1-2 sentences).
3. Provide the IDEAL answer (MAX 2-3 sentences, direct and concise).

RETURN JSON ONLY:
{{
    "score": int,
    "feedback": "string",
    "missing_keywords": ["list", "of", "key", "terms"],
    "improvements": "string",
    "ideal_answer": "string (Max 2-3 sentences)"
}}"""

        try:
            response_text = run_genai_with_rotation(prompt, is_json=True)
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            data = json.loads(text.strip())
            gemini_score = float(data.get("score", 5))
            ideal = data.get("ideal_answer", "")

            tfidf = calculate_tfidf_score(answer, ideal)
            h_score = _hybrid_score(gemini_score, tfidf["relevance_score"])

            return EvaluationResult(
                score=h_score,
                feedback=data.get("feedback", "No feedback."),
                missing_keywords=data.get("missing_keywords", []),
                improvements=data.get("improvements", ""),
                ideal_answer=ideal,
                ml_relevance_score=tfidf["relevance_score"],
                ml_relevance_grade=tfidf["grade"],
                hybrid_score=h_score
            )
        except Exception as e:
            print(f"Single evaluation failed: {e}. Falling back to local hybrid.")
            local = self._evaluate_one_local({
                "question": question,
                "answer": answer,
                "type": "technical",
                "difficulty": "medium",
                "keywords": context_keywords if context_keywords else None
            })
            return EvaluationResult(
                score=local["score"],
                feedback=local["feedback"],
                missing_keywords=local["missing_keywords"],
                improvements=local["improvements"],
                ideal_answer=local["ideal_answer"],
                ml_relevance_score=local["ml_relevance_score"],
                ml_relevance_grade=local["ml_relevance_grade"],
                hybrid_score=local["hybrid_score"]
            )


if __name__ == "__main__":
    evaluator = AnswerEvaluator()
    res = evaluator.evaluate(
        "What is React?",
        "React is a JavaScript library for building user interfaces using components and reusable UI logic.",
        ["react", "javascript", "components", "user interfaces"]
    )
    print(f"Score: {res.score}, Feedback: {res.feedback}")