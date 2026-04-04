#question_generator.py
from enum import unique
import os
import json
import typing_extensions
import google.generativeai as genai
from dotenv import load_dotenv

class Question(typing_extensions.TypedDict):
    id: int
    text: str
    type: str
    difficulty: str
    context: str
    initial_code: typing_extensions.NotRequired[str]
    keywords: typing_extensions.NotRequired[list[str]]
    ideal_answer: typing_extensions.NotRequired[str]

class InterviewScript(typing_extensions.TypedDict):
    questions: list[Question]

class QuestionGenerator:
    def __init__(self):
        pass

    def _dedupe_questions(self, questions: list) -> list:
        seen = set()
        unique_qs = []
        for q in questions:
            text = q.get("text", "").strip().lower()
            normalized = " ".join(text.split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_qs.append(q)
        for i, q in enumerate(unique_qs, start=1):
            q["id"] = i
        return unique_qs

    def generate_questions(
            self,
            resume_text: str,
            num_questions: int = 5,
            difficulty: str = "mixed",
            job_description: str = "",
            auto_select_count: bool = False,
            experience_context: str = ""   # NEW: injected from main.py
            ) -> list:
        num_questions = max(3, min(num_questions, 20))
        if auto_select_count:
            num_questions = 8

        difficulty_instruction = (
            "Use a realistic mix of easy, medium, and hard questions."
            if difficulty == "mixed"
            else f"Target difficulty: {difficulty}. Keep MOST questions at {difficulty} difficulty."
        )

        quantity_instruction = (
            f"Generate EXACTLY {num_questions} questions. "
            f"The JSON output MUST contain EXACTLY {num_questions} unique questions."
        )

        has_jd = bool((job_description or "").strip())
        job_desc_section = (
            f"--- JOB DESCRIPTION ---\n{job_description[:3000]}\n---"
            if has_jd else
            "No job description provided."
        )

        if has_jd:
            source_instruction = f"""
QUESTION SOURCE DISTRIBUTION (MANDATORY):
For the {num_questions} questions, infer the candidate's most likely target role from:
- projects, skills, tools/frameworks, work/internship experience, optional job description

Then generate questions using this balanced structure:
1. Intro/background question (exactly 1)
2. Motivation / career direction question (exactly 1)
3. Resume project deep-dive questions (at least 30%)
4. Skills/tools/concepts questions inferred from resume (at least 30%)
5. JD-aligned requirement questions (at least 20% when JD exists)
6. Final closing / value proposition question (exactly 1)

IMPORTANT:
- Infer the likely role internally from resume/JD.
- DO NOT repeat or paraphrase the same question.
"""
        else:
            source_instruction = f"""
QUESTION SOURCE DISTRIBUTION (MANDATORY):
For the {num_questions} questions, infer the candidate's most likely target role from:
- projects, skills, tools/frameworks, work/internship experience

Then generate questions using this balanced structure:
1. Intro/background question (exactly 1)
2. Motivation / career direction question (exactly 1)
3. Resume project deep-dive questions (at least 40%)
4. Skills/tools/concepts questions inferred from resume (at least 40%)
5. Final closing / value proposition question (exactly 1)

IMPORTANT:
- Infer the likely role internally from resume.
- DO NOT repeat or paraphrase the same question.
"""

        # Inject experience context if provided
        experience_section = f"\n{experience_context}\n" if experience_context else ""

        prompt = f"""
You are an expert technical interviewer.

TASK:
Generate a high-quality mock interview question set from the candidate's resume and optional job description.

RULES:
- Return ONLY valid raw JSON.
- No markdown. No explanations.
- Output format must be:
{{
  "questions": [
    {{
      "id": 1,
      "text": "question text",
      "type": "technical",
      "difficulty": "medium",
      "context": "why this question is relevant",
      "initial_code": ""
    }}
  ]
}}

GLOBAL REQUIREMENTS:
- {quantity_instruction}
- {difficulty_instruction}
- Allowed types: technical, behavioral, coding
- Each question must be unique
- No duplicate or near-duplicate questions
- Make questions feel like a real interview flow
- Include coding questions only when the resume strongly supports it

{experience_section}
{source_instruction}

--- RESUME ---
{resume_text[:8000]}
---

{job_desc_section}
"""

        from ai_utils import run_genai_with_rotation
        from question_bank import get_fallback_questions

        try:
            response_text = run_genai_with_rotation(prompt, is_json=True)
            text = response_text.strip()
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            questions = []
            if isinstance(data, dict) and "questions" in data:
                questions = data["questions"]
            elif isinstance(data, list):
                questions = data

            if not isinstance(questions, list):
                raise ValueError("Gemini did not return a valid questions list")

            normalized = []
            for i, q in enumerate(questions, start=1):
                normalized.append({
                    "id": i,
                    "text": str(q.get("text", "")).strip(),
                    "type": str(q.get("type", "technical")).lower(),
                    "difficulty": str(q.get("difficulty", "medium")).lower(),
                    "context": str(q.get("context", "Resume/JD aligned question")).strip(),
                    "initial_code": str(q.get("initial_code", "") or "")
                })

            normalized = [q for q in normalized if q["text"]]
            normalized = self._dedupe_questions(normalized)
            normalized = self._enforce_interview_structure(normalized, num_questions)

            if len(normalized) < num_questions:
                fallback_fill = get_fallback_questions(resume_text=resume_text, num_questions=num_questions)
                existing = {q["text"].strip().lower() for q in normalized}
                for fq in fallback_fill:
                    txt = fq["text"].strip().lower()
                    if txt not in existing:
                        normalized.append(fq)
                        existing.add(txt)
                    if len(normalized) >= num_questions:
                        break

            final_questions = normalized[:num_questions]
            for idx, q in enumerate(final_questions, start=1):
                q["id"] = idx

            print(f"Generated {len(final_questions)} questions successfully")
            return final_questions

        except Exception as e:
            print(f"Question Generation AI failed: {e}. Using fallback questions.")
            return get_fallback_questions(resume_text=resume_text, num_questions=num_questions)

    def _enforce_interview_structure(self, questions: list, num_questions: int) -> list:
        if not questions:
            return questions

        intro_keywords = ["tell me about yourself", "walk me through your background",
                         "introduce yourself", "background", "what interested you"]
        closing_keywords = ["why hire you", "why should we hire", "what unique value",
                           "great fit for this role", "wrap up", "any questions for"]

        def is_intro(q): return any(k in q.get("text", "").lower() for k in intro_keywords)
        def is_closing(q): return any(k in q.get("text", "").lower() for k in closing_keywords)

        first_is_intro = is_intro(questions[0])
        last_is_closing = len(questions) > 2 and is_closing(questions[-1])

        if first_is_intro and (len(questions) <= 2 or last_is_closing):
            for idx, q in enumerate(questions, start=1): q["id"] = idx
            return questions[:num_questions]

        intro_q = None
        closing_q = None
        middle = []

        for q in questions:
            if is_intro(q) and not intro_q: intro_q = q
            elif is_closing(q) and not closing_q: closing_q = q
            else: middle.append(q)

        if not intro_q:
            intro_q = {
                "id": 1, "text": "To get us started, could you walk me through your background and the kinds of opportunities you're targeting right now?",
                "type": "behavioral", "difficulty": "easy",
                "context": "[Resume] Opening question to establish rapport", "initial_code": ""
            }
        if not closing_q and num_questions > 2:
            closing_q = {
                "id": 999, "text": "Before we wrap up, why do you think you'd be a great fit for this role, and what unique value would you bring to our team?",
                "type": "behavioral", "difficulty": "medium",
                "context": "[Role] Closing question to assess self-awareness and fit", "initial_code": ""
            }

        final = [intro_q]
        target_middle = num_questions - (2 if closing_q else 1)
        final.extend(middle[:target_middle])
        if closing_q: final.append(closing_q)

        for idx, q in enumerate(final, start=1): q["id"] = idx
        return final[:num_questions]


if __name__ == "__main__":
    gen = QuestionGenerator()
    print("QuestionGenerator initialized.")