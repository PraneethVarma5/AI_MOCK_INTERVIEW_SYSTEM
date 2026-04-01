from enum import unique
import os
import json
import typing_extensions
import google.generativeai as genai
from dotenv import load_dotenv

# Use TypedDict for schema definition as it's often more reliable for simple JSON constraints with Gemini
class Question(typing_extensions.TypedDict):
    id: int
    text: str
    type: str  # "technical" | "behavioral" | "coding"
    difficulty: str  # "easy" | "medium" | "hard"
    context: str
    initial_code: typing_extensions.NotRequired[str]
    keywords: typing_extensions.NotRequired[list[str]]
    ideal_answer: typing_extensions.NotRequired[str]

class InterviewScript(typing_extensions.TypedDict):
    questions: list[Question]

class QuestionGenerator:
    def __init__(self):
        # Configuration is now handled by ai_utils dynamically
        pass

    def _dedupe_questions(self, questions: list[Question]) -> list[Question]:
        seen = set()
        unique = []
        for q in questions:
            text = q.get("text", "").strip().lower()
            normalized = " ".join(text.split())

            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(q)

    # Reassign IDs cleanly
        for i, q in enumerate(unique, start=1):
            q["id"] = i

        return unique
    
    def generate_questions(
            self,
            resume_text: str,
            num_questions: int = 5,
            difficulty: str = "mixed",
            job_description: str = "",
            auto_select_count: bool = False
            ) -> list[Question]:
        num_questions = max(3, min(num_questions, 20))
        # Auto mode
        if auto_select_count:
            num_questions = 8  # safe default for auto mode

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
    - projects
    - skills
    - tools/frameworks
    - work/internship experience
    - optional job description

    Then generate questions using this balanced structure:
    1. Intro/background question (exactly 1)
    2. Motivation / career direction question (exactly 1)
    3. Resume project deep-dive questions (at least 30%)
    4. Skills/tools/concepts questions inferred from resume (at least 30%)
    5. JD-aligned requirement questions (at least 20% when JD exists)
    6. Final closing / value proposition question (exactly 1)

    IMPORTANT:
    - Do NOT depend on a manually supplied role.
    - Infer the likely role internally.
    - Questions must reflect the candidate's strongest fit based on the resume and JD.
    - If multiple roles are possible, prioritize the dominant one and allow 1-2 cross-functional questions.
    - DO NOT repeat or paraphrase the same question.
    """
        else:
            source_instruction = f"""
    QUESTION SOURCE DISTRIBUTION (MANDATORY):
    For the {num_questions} questions, infer the candidate's most likely target role from:
    - projects
    - skills
    - tools/frameworks
    - work/internship experience

    Then generate questions using this balanced structure:
    1. Intro/background question (exactly 1)
    2. Motivation / career direction question (exactly 1)
    3. Resume project deep-dive questions (at least 40%)
    4. Skills/tools/concepts questions inferred from resume (at least 40%)
    5. Final closing / value proposition question (exactly 1)

    IMPORTANT:
    - Do NOT depend on a manually supplied role.
    - Infer the likely role internally.
    - Questions must reflect the candidate's strongest fit based on the resume.
    - If multiple roles are possible, prioritize the dominant one and allow 1-2 cross-functional questions.
    - DO NOT repeat or paraphrase the same question.
    """

        prompt = f"""
    You are an expert technical interviewer.

    TASK:
    Generate a high-quality mock interview question set from the candidate's resume and optional job description.

    RULES:
    - Return ONLY valid raw JSON.
    - No markdown.
    - No explanations.
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
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)

            questions = []
            if isinstance(data, dict) and "questions" in data:
                questions = data["questions"]
            elif isinstance(data, list):
                questions = data

            if not isinstance(questions, list):
                raise ValueError("Gemini did not return a valid questions list")

            # Normalize
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

            # Remove empties + dedupe
            normalized = [q for q in normalized if q["text"]]
            normalized = self._dedupe_questions(normalized)

            # Enforce structure
            normalized = self._enforce_interview_structure(normalized, num_questions)

            # If Gemini still returned too few, fill safely
            if len(normalized) < num_questions:
                fallback_fill = get_fallback_questions(
                    resume_text=resume_text,
                    num_questions=num_questions
                )
                existing = {q["text"].strip().lower() for q in normalized}
                for fq in fallback_fill:
                    txt = fq["text"].strip().lower()
                    if txt not in existing:
                        normalized.append(fq)
                        existing.add(txt)
                    if len(normalized) >= num_questions:
                        break

            # Final trim + re-id
            final_questions = normalized[:num_questions]
            for idx, q in enumerate(final_questions, start=1):
                q["id"] = idx

            print(f"Generated {len(final_questions)} questions successfully")
            return final_questions

        except Exception as e:
            print(f"Question Generation AI failed: {e}. Using fallback questions.")
            return get_fallback_questions(
                resume_text=resume_text,
                num_questions=num_questions
            )
        
    def _enforce_interview_structure(self, questions: list, num_questions: int) -> list:
        """
        Validates and enforces realistic interview structure.
        Only adds genuinely missing intro/closing from the static bank — does NOT cycle/clone questions.
        """
        if not questions or len(questions) == 0:
            return questions
        
        # Define intro question patterns
        intro_keywords = ["tell me about yourself", "walk me through your background", 
                         "introduce yourself", "background", "what interested you"]
        
        # Define closing question patterns
        closing_keywords = ["why hire you", "why should we hire", "what unique value", 
                           "great fit for this role", "wrap up", "any questions for"]
        
        def is_intro_question(q: dict) -> bool:
            text_lower = q.get("text", "").lower()
            return any(keyword in text_lower for keyword in intro_keywords)
        
        def is_closing_question(q: dict) -> bool:
            text_lower = q.get("text", "").lower()
            return any(keyword in text_lower for keyword in closing_keywords)
        
        # Check if first question is intro
        first_is_intro = is_intro_question(questions[0])
        
        # Check if last question is closing (only if we have more than 2 questions)
        last_is_closing = False
        if len(questions) > 2:
            last_is_closing = is_closing_question(questions[-1])
        
        # If structure is already correct, just reassign IDs and return
        if first_is_intro and (len(questions) <= 2 or last_is_closing):
            for idx, q in enumerate(questions, start=1):
                q["id"] = idx
            print(f"Interview structure validated: Intro -> {len(questions)-2} middle -> Closing")
            return questions[:num_questions]
        
        # Structure needs mild fixing — rearrange without cloning
        print(f"Fixing interview structure (intro: {first_is_intro}, closing: {last_is_closing})")
        
        intro_q = None
        closing_q = None
        middle_questions = []
        
        # Extract intro, closing, and middle questions
        for q in questions:
            if is_intro_question(q) and not intro_q:
                intro_q = q
            elif is_closing_question(q) and not closing_q:
                closing_q = q
            else:
                middle_questions.append(q)
        
        # Create default intro if missing
        if not intro_q:
            intro_q = {
                "id": 1,
                "text": "To get us started, could you walk me through your background and the kinds of opportunities you're targeting right now?",
                "type": "behavioral",
                "difficulty": "easy",
                "context": "[Resume] Opening question to establish rapport",
                "initial_code": ""
            }
            print("  Added missing intro question")
        
        # Create default closing if missing and we have enough questions
        if not closing_q and num_questions > 2:
            closing_q = {
                "id": 999,
                "text": "Before we wrap up, why do you think you'd be a great fit for this role, and what unique value would you bring to our team?",
                "type": "behavioral",
                "difficulty": "medium",
                "context": "[Role] Closing question to assess self-awareness and fit",
                "initial_code": ""
            }
            print("  Added missing closing question")
        
        # Rebuild the question list — NO cloning/cycling
        final_questions = [intro_q]
        target_middle_count = num_questions - (2 if closing_q else 1)
        final_questions.extend(middle_questions[:target_middle_count])
        
        if closing_q:
            final_questions.append(closing_q)
        
        # Reassign IDs sequentially
        for idx, q in enumerate(final_questions, start=1):
            q["id"] = idx
        
        print(f"Restructured to: Intro -> {len(final_questions)-2 if closing_q else len(final_questions)-1} middle -> {'Closing' if closing_q else 'No closing'}")
        return final_questions[:num_questions]
def _normalize_question_text(self, text: str) -> str:
    import re
    text = (text or "").lower().strip()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def _dedupe_questions(self, questions: list, num_questions: int, role: str) -> list:
    seen = set()
    unique = []

    for q in questions:
        norm = self._normalize_question_text(q.get("text", ""))
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique.append(q)

    # If AI still returned too few, fill with safe unique questions
    fillers = [
        {
            "text": f"Could you walk me through a project from your background that best reflects your readiness for this {role} role?",
            "type": "technical",
            "difficulty": "medium",
            "context": "[Resume] Project depth",
            "initial_code": ""
        },
        {
            "text": "How do you approach debugging when the issue is intermittent and hard to reproduce?",
            "type": "technical",
            "difficulty": "medium",
            "context": "[Role] Debugging approach",
            "initial_code": ""
        },
        {
            "text": "Tell me about a time you had to pick between speed of delivery and code quality. What did you do?",
            "type": "behavioral",
            "difficulty": "medium",
            "context": "[Role] Tradeoff thinking",
            "initial_code": ""
        }
    ]

    for filler in fillers:
        if len(unique) >= num_questions:
            break
        norm = self._normalize_question_text(filler["text"])
        if norm not in seen:
            seen.add(norm)
            unique.append(filler.copy())

    for idx, q in enumerate(unique[:num_questions], start=1):
        q["id"] = idx

    return unique[:num_questions]

if __name__ == "__main__":
    # Quick sanity check
    gen = QuestionGenerator()
    params = {"resume_text": "Experience with Python, Django, and React.", "role": "Full Stack Dev"}
    print("QuestionGenerator initialized.")
