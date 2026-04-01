from typing import List, Dict, Any

# A static collection of high-quality interview questions for common stacks
# This serves as the Level 3 (Final) fallback when all AI models hit quota limits.

QUESTION_BANK: Dict[str, List[Dict[str, Any]]] = {
    "python": [
        {
            "id": 1001,
            "text": "For a start, I see you've worked with Python. If you were explaining the practical difference between a list and a tuple to a junior developer, how would you describe when it's absolutely critical to use one over the other?",
            "type": "technical",
            "difficulty": "easy",
            "context": "Core Python proficiency with a conversational lens.",
            "initial_code": ""
        },
        {
            "id": 1002,
            "text": "I'm curious about your experience with advanced Python features. How have you used decorators in your previous projects to clean up or extend your code's functionality?",
            "type": "technical",
            "difficulty": "medium",
            "context": "Advanced Python concepts in a practical context.",
            "initial_code": ""
        },
        {
            "id": 1003,
            "text": "Let's look at a quick coding scenario. Could you write a short function for me that takes a string and returns it reversed? For example, 'hello' becoming 'olleh'.",
            "type": "coding",
            "difficulty": "easy",
            "context": "Basic algorithmic thinking.",
            "initial_code": "def reverse_string(s):\n    # Your code here\n    pass"
        }
    ],
    "javascript": [
        {
            "id": 2001,
            "text": "What is the difference between '==' and '===' in JavaScript?",
            "type": "technical",
            "difficulty": "easy",
            "context": "JS fundamentals.",
            "initial_code": ""
        },
        {
            "id": 2002,
            "text": "Explain the concept of 'closures' in JavaScript with an example.",
            "type": "technical",
            "difficulty": "medium",
            "context": "Scope and memory management in JS.",
            "initial_code": ""
        },
        {
            "id": 2003,
            "text": "Write a function that filters an array of numbers to return only the even ones.",
            "type": "coding",
            "difficulty": "easy",
            "context": "Array manipulation in JS.",
            "initial_code": "function filterEvens(arr) {\n    // Your code here\n}"
        }
    ],
    "react": [
        {
            "id": 3001,
            "text": "What are React Hooks? Explain useState and useEffect.",
            "type": "technical",
            "difficulty": "easy",
            "context": "Modern React development.",
            "initial_code": ""
        },
        {
            "id": 3002,
            "text": "What is the Virtual DOM, and how does React use it to improve performance?",
            "type": "technical",
            "difficulty": "medium",
            "context": "React architecture.",
            "initial_code": ""
        }
    ],
    "general_technical": [
        {
            "id": 5001,
            "text": "Could you walk me through your debugging process? For example, when you hit a complex bug that isn't immediately obvious, what steps do you take to isolate the root cause?",
            "type": "technical",
            "difficulty": "medium",
            "context": "Debugging and problem-solving methodology.",
            "initial_code": ""
        },
        {
            "id": 5002,
            "text": "How do you approach testing your code? Do you lean more towards unit testing, integration testing, or a mix, and why?",
            "type": "technical",
            "difficulty": "easy",
            "context": "Quality assurance mindset.",
            "initial_code": ""
        },
        {
            "id": 5003,
            "text": "When picking a new tool or library for a project, what criteria do you look for to decide if it's the right choice?",
            "type": "technical",
            "difficulty": "medium",
            "context": "Tech stack decision making.",
            "initial_code": ""
        }
    ],
    "general_behavioral": [
        {
            "id": 4001,
            "text": "I'd love to hear about a project that really challenged you. What was the biggest hurdle you hit, and how did you navigate through it to get the results you wanted?",
            "type": "behavioral",
            "difficulty": "medium",
            "context": "Problem-solving and resilience.",
            "initial_code": ""
        },
        {
            "id": 4002,
            "text": "Thinking about your future, where do you see your career heading in the next couple of years, particularly in terms of the technical skills you want to master?",
            "type": "behavioral",
            "difficulty": "easy",
            "context": "Ambition and career alignment.",
            "initial_code": ""
        },
        {
            "id": 4003,
            "text": "We all hit points of friction in a team. Could you share a time when you disagreed with a teammate? How did you approach that conversation to find a path forward?",
            "type": "behavioral",
            "difficulty": "easy",
            "context": "Conflict resolution and teamwork.",
            "initial_code": ""
        },
        {
            "id": 4004,
            "text": "Can you describe a specific time you had to learn a new technology quickly to get a job done? How did you go about it?",
            "type": "behavioral",
            "difficulty": "medium",
            "context": "Adaptability and learning agility.",
            "initial_code": ""
        }
    ]
}

def get_fallback_questions(resume_text: str, role: str = "Software Engineer", num_questions: int = 5) -> List[Dict[str, Any]]:
    """
    Fallback question generator without repeating exact questions.
    Tries to balance intro + unique middle + closing.
    """
    resume_lower = resume_text.lower()

    intro_question = {
        "id": 1,
        "text": f"To get us started, could you walk me through your background and what specifically interested you about this {role} position?",
        "type": "behavioral",
        "difficulty": "easy",
        "context": "[Role] Opening question to establish rapport",
        "initial_code": ""
    }

    closing_question = {
        "id": 9999,
        "text": "Before we wrap up, why do you think you'd be a great fit for this role, and what unique value would you bring to our team?",
        "type": "behavioral",
        "difficulty": "medium",
        "context": "[Role] Closing question to assess self-awareness and fit",
        "initial_code": ""
    }

    candidate_questions = []
    seen_texts = set()

    # Skill-based questions from resume
    for skill, questions in QUESTION_BANK.items():
        if skill not in ["general_behavioral", "general_technical"] and skill in resume_lower:
            for q in questions:
                txt = q["text"].strip().lower()
                if txt not in seen_texts:
                    candidate_questions.append(q)
                    seen_texts.add(txt)

    # If no resume skill match, use a mixed safe fallback
    if not candidate_questions:
        for bucket in ["python", "javascript", "react", "general_technical"]:
            for q in QUESTION_BANK.get(bucket, []):
                txt = q["text"].strip().lower()
                if txt not in seen_texts:
                    candidate_questions.append(q)
                    seen_texts.add(txt)

    # Add general behavioral + technical (unique only)
    for bucket in ["general_technical", "general_behavioral"]:
        for q in QUESTION_BANK.get(bucket, []):
            txt = q["text"].strip().lower()
            if txt not in seen_texts:
                candidate_questions.append(q)
                seen_texts.add(txt)

    final_questions = [intro_question]

    # Middle slots
    needed_middle = max(0, num_questions - 2)
    middle_unique = candidate_questions[:needed_middle]
    final_questions.extend(middle_unique)

    # If still short, add handcrafted non-repeating generic fillers
    generic_fillers = [
    {
        "text": "Walk me through a project where you had to debug something tricky. How did you isolate the root cause?",
        "type": "technical",
        "difficulty": "medium",
        "context": "[Resume] Problem-solving and debugging depth",
        "initial_code": ""
    },
    {
        "text": "How do you decide when to optimize code versus keeping the implementation simple and readable?",
        "type": "technical",
        "difficulty": "medium",
        "context": "[Role] Engineering trade-off judgment",
        "initial_code": ""
    },
    {
        "text": "Tell me about a time you had to learn a new tool or framework quickly to finish a project.",
        "type": "behavioral",
        "difficulty": "easy",
        "context": "[Resume] Adaptability and learning speed",
        "initial_code": ""
    },
    {
        "text": "When working on a feature end-to-end, how do you validate that it’s actually production-ready?",
        "type": "technical",
        "difficulty": "medium",
        "context": "[Role] Testing and deployment mindset",
        "initial_code": ""
    },
    {
        "text": "Describe a time when you disagreed with a technical decision. How did you handle it?",
        "type": "behavioral",
        "difficulty": "medium",
        "context": "[Role] Communication and team collaboration",
        "initial_code": ""
    },
    {
        "text": "How do you approach designing a solution when the requirements are incomplete or ambiguous?",
        "type": "technical",
        "difficulty": "hard",
        "context": "[Role] Ambiguity handling",
        "initial_code": ""
    },
    {
        "text": "Tell me about a project where performance became a problem. What did you measure and what did you change?",
        "type": "technical",
        "difficulty": "hard",
        "context": "[Resume] Performance optimization",
        "initial_code": ""
    },
    {
        "text": "How do you structure your code so that it remains maintainable as a project grows?",
        "type": "technical",
        "difficulty": "medium",
        "context": "[Role] Maintainability",
        "initial_code": ""
    },
    {
        "text": "Describe a time you had to balance delivery speed with quality. What trade-offs did you make?",
        "type": "behavioral",
        "difficulty": "medium",
        "context": "[Role] Trade-off judgment",
        "initial_code": ""
    },
    {
        "text": "How do you verify that a bug is truly fixed and won’t regress later?",
        "type": "technical",
        "difficulty": "medium",
        "context": "[Role] Validation and testing",
        "initial_code": ""
    },
    {
        "text": "What is your approach to writing clean, readable, and review-friendly code?",
        "type": "technical",
        "difficulty": "easy",
        "context": "[Role] Code quality",
        "initial_code": ""
    },
    {
        "text": "Tell me about a time you improved a project beyond the minimum requirements. Why did you do it?",
        "type": "behavioral",
        "difficulty": "easy",
        "context": "[Resume] Initiative and ownership",
        "initial_code": ""
    },
    {
        "text": "How do you choose between multiple tools, libraries, or frameworks for the same task?",
        "type": "technical",
        "difficulty": "medium",
        "context": "[Role] Technical decision making",
        "initial_code": ""
    },
    {
        "text": "Describe a situation where your first solution failed. How did you recover and improve it?",
        "type": "behavioral",
        "difficulty": "medium",
        "context": "[Resume] Resilience and iteration",
        "initial_code": ""
    },
    {
        "text": "How do you think about scalability when building a feature that may grow over time?",
        "type": "technical",
        "difficulty": "hard",
        "context": "[Role] Scalability thinking",
        "initial_code": ""
    }
]
    
    filler_idx = 0
    while len(final_questions) < (num_questions - 1) and filler_idx < len(generic_fillers):
        filler = generic_fillers[filler_idx].copy()
        filler["id"] = 10000 + filler_idx
        final_questions.append(filler)
        filler_idx += 1

    if num_questions > 1:
        final_questions.append(closing_question)

    for idx, q in enumerate(final_questions[:num_questions], start=1):
        q["id"] = idx

    return final_questions[:num_questions]