"""
db_init.py — Run this ONCE to create and seed the SQLite database.
Usage: python db_init.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "interview.db")

TARGET_MIN_HR = 60
TARGET_MIN_PER_ROLE = 50

def dedupe_questions(question_tuples):
    seen = set()
    unique = []
    for q in question_tuples:
        key = q[0].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique

def expand_hr_questions(base_questions):
    extra_questions = [
        ("Tell me about a time you had to learn a new skill quickly.", "behavioral", "medium"),
        ("Describe a situation where you had to manage competing deadlines.", "behavioral", "medium"),
        ("Tell me about a time you had to work with an unclear requirement.", "behavioral", "hard"),
        ("Describe a time you had to recover from a mistake.", "behavioral", "medium"),
        ("Tell me about a time you improved a process at work or college.", "behavioral", "medium"),
        ("Describe a time you had to handle a difficult stakeholder.", "behavioral", "hard"),
        ("Tell me about a time you took initiative without formal authority.", "behavioral", "medium"),
        ("Describe a time you had to adapt your communication style for someone else.", "behavioral", "medium"),
        ("Tell me about a time you had to prioritize under pressure.", "behavioral", "medium"),
        ("Describe a time you had to make a decision with incomplete information.", "behavioral", "hard"),
        ("Tell me about a time you disagreed with a team decision.", "behavioral", "medium"),
        ("Describe a time you had to ask for help to complete something important.", "behavioral", "easy"),
        ("Tell me about a time you handled failure and bounced back.", "behavioral", "medium"),
        ("Describe a time you had to deliver quality work in limited time.", "behavioral", "hard"),
        ("Tell me about a time you motivated yourself during a difficult period.", "behavioral", "easy"),
        ("Describe a time you had to collaborate with someone very different from you.", "behavioral", "medium"),
        ("Tell me about a time you had to manage expectations proactively.", "behavioral", "medium"),
        ("Describe a time you had to persuade someone to support your idea.", "behavioral", "hard"),
        ("Tell me about a time you had to balance speed vs quality.", "behavioral", "hard"),
        ("Describe a time you received tough feedback and applied it.", "behavioral", "medium"),
        ("Tell me about a time you had to work outside your comfort zone.", "behavioral", "medium"),
        ("Describe a time you had to resolve a misunderstanding.", "behavioral", "medium"),
        ("Tell me about a time you improved team communication.", "behavioral", "medium"),
        ("Describe a time you had to take ownership of a problem end-to-end.", "behavioral", "medium"),
        ("Tell me about a time you had to make a trade-off between two important priorities.", "behavioral", "hard"),
        ("Describe a time you had to handle repetitive work while maintaining accuracy.", "behavioral", "easy"),
        ("Tell me about a time you mentored or helped someone improve.", "behavioral", "medium"),
        ("Describe a time you handled ambiguity successfully.", "behavioral", "hard"),
        ("Tell me about a time you built trust with a new team or stakeholder.", "behavioral", "medium"),
        ("Describe a time you had to deliver bad news professionally.", "behavioral", "hard"),
        ("Tell me about a time you had to stay calm in a stressful situation.", "behavioral", "medium"),
        ("Describe a time you solved a problem creatively.", "behavioral", "medium"),
        ("Tell me about a time you had to defend a decision you made.", "behavioral", "hard"),
        ("Describe a time you learned something from a failed attempt.", "behavioral", "medium"),
        ("Tell me about a time you had to work independently for a long period.", "behavioral", "easy"),
    ]

    questions = dedupe_questions(base_questions + extra_questions)
    return questions[:TARGET_MIN_HR]

def expand_role_questions(role_name, base_questions):
    generic_role_questions = [
    ("Walk me through a challenging technical problem you solved in this domain.", "technical", "medium"),
    ("How do you approach debugging a difficult issue in your work?", "technical", "medium"),
    ("What trade-offs do you consider when making technical decisions?", "technical", "hard"),
    ("How do you validate that your solution is correct before shipping?", "technical", "medium"),
    ("How do you break down a large technical problem into smaller tasks?", "technical", "medium"),
    ("What metrics would you use to judge success in this role?", "technical", "medium"),
    ("What common mistakes do people make in this role, and how do you avoid them?", "technical", "medium"),
    ("What tools or frameworks would you choose first for a new project in this role, and why?", "technical", "medium"),
    ("How do you ensure your work remains maintainable over time?", "technical", "hard"),
    ("Walk me through how you would review or validate someone else's work in this domain.", "technical", "medium"),
    ("How do you estimate effort or complexity for a task in this role?", "technical", "medium"),
    ("How do you balance short-term delivery with long-term technical quality?", "technical", "hard"),
    ("Walk me through a realistic scenario relevant to this role and how you would handle it.", "technical", "medium"),
    ("How do you decide when to simplify versus optimize a solution?", "technical", "hard"),
    ("What risks do you look for early in a project in this role?", "technical", "medium"),
    ("How do you measure whether a solution is truly successful after launch or delivery?", "technical", "medium"),
    ("How do you choose between multiple possible technical approaches for the same problem?", "technical", "hard"),
    ("How would you improve the performance, scalability, or reliability of an existing system in this domain?", "technical", "hard"),
    ("What does a high-quality implementation look like in this role?", "technical", "medium"),
    ("How do you design for edge cases and failure scenarios in this role?", "technical", "hard"),
    ("What are the most important best practices you follow in this role?", "technical", "medium"),
    ("How do you verify that your solution handles real-world usage patterns?", "technical", "medium"),
    ("How do you reason about performance bottlenecks in this domain?", "technical", "hard"),
    ("How do you ensure your implementation is secure, reliable, and maintainable?", "technical", "hard"),
    ("How would you explain the architecture of a strong project in this role?", "technical", "medium"),
    ("What signals tell you that a design or implementation needs refactoring?", "technical", "medium"),
    ("How do you compare two competing tools or frameworks for a project in this role?", "technical", "medium"),
    ("How do you make technical decisions when requirements are incomplete?", "technical", "hard"),
    ("What kinds of tests or validation steps are most important in this role?", "technical", "medium"),
    ("How do you handle trade-offs between performance, maintainability, and delivery speed?", "technical", "hard"),
    ("How do you identify the highest-risk part of a solution before implementation?", "technical", "medium"),
    ("How would you approach improving an underperforming feature or system in this role?", "technical", "medium"),
    ("How do you ensure your solution is production-ready or deployment-ready?", "technical", "hard"),
    ("What technical habits make someone strong in this role?", "technical", "easy"),
    ("How do you decide what should be abstracted versus kept simple in a solution?", "technical", "hard"),
]


    questions = dedupe_questions(base_questions + generic_role_questions)

    # If still somehow short, add safe generic variants
    counter = 1
    while len(questions) < TARGET_MIN_PER_ROLE:
        questions.append((
            f"Walk through another realistic {role_name} scenario and how you would handle it. (Variation {counter})",
            "technical",
            "medium"
        ))
        counter += 1

    return questions[:TARGET_MIN_PER_ROLE]

HR_QUESTIONS = [
    # Easy
    ("Tell me about yourself and your professional journey so far.", "behavioral", "easy"),
    ("Why are you looking for a new opportunity at this time?", "behavioral", "easy"),
    ("What are your greatest strengths and how do they help you at work?", "behavioral", "easy"),
    ("Describe your ideal work environment.", "behavioral", "easy"),
    ("How do you prioritize tasks when you have multiple deadlines?", "behavioral", "easy"),
    ("What motivates you to do your best work?", "behavioral", "easy"),
    ("How do you handle constructive criticism from your manager?", "behavioral", "easy"),
    ("Tell me about a time you went above and beyond at work.", "behavioral", "easy"),
    ("What are you most proud of in your career so far?", "behavioral", "easy"),
    ("Where do you see yourself in 5 years?", "behavioral", "easy"),
    # Medium
    ("Describe a time you had a conflict with a coworker. How did you resolve it?", "behavioral", "medium"),
    ("Tell me about a time you had to adapt quickly to a major change at work.", "behavioral", "medium"),
    ("Give an example of a goal you set and how you achieved it.", "behavioral", "medium"),
    ("Describe a situation where you had to work with limited resources.", "behavioral", "medium"),
    ("Tell me about a time you made a significant mistake and what you learned from it.", "behavioral", "medium"),
    ("How do you handle working under pressure or tight deadlines?", "behavioral", "medium"),
    ("Describe a time you had to persuade someone to see your point of view.", "behavioral", "medium"),
    ("Tell me about a time you took initiative without being asked.", "behavioral", "medium"),
    ("How do you handle situations where you disagree with your manager's decision?", "behavioral", "medium"),
    ("Describe your leadership style with a concrete example.", "behavioral", "medium"),
    # Hard
    ("Tell me about the most difficult decision you've had to make at work and its outcome.", "behavioral", "hard"),
    ("Describe a time you had to lead a team through a crisis or major setback.", "behavioral", "hard"),
    ("Give an example of when you had to balance competing priorities with no good answer.", "behavioral", "hard"),
    ("Tell me about a time you had to give difficult feedback to a peer or report.", "behavioral", "hard"),
    ("Describe a time you had to rebuild trust with a stakeholder after a failure.", "behavioral", "hard"),
]

ROLE_QUESTIONS = {
    "Software Engineer": [
        ("What is the difference between a process and a thread?", "technical", "medium"),
        ("Explain the concept of time and space complexity with an example.", "technical", "medium"),
        ("What is a RESTful API and what are its key constraints?", "technical", "easy"),
        ("Explain the SOLID principles of object-oriented design.", "technical", "hard"),
        ("What is the difference between SQL and NoSQL databases? When would you use each?", "technical", "medium"),
        ("Describe how you would design a URL shortening service.", "technical", "hard"),
        ("What is a deadlock? How do you prevent it?", "technical", "hard"),
        ("Explain the difference between authentication and authorization.", "technical", "easy"),
        ("What is Docker and why is it useful in software development?", "technical", "medium"),
        ("What is the difference between unit testing, integration testing, and end-to-end testing?", "technical", "medium"),
        ("How does garbage collection work in a language of your choice?", "technical", "hard"),
        ("Explain the CAP theorem.", "technical", "hard"),
        ("What is CI/CD and why is it important?", "technical", "easy"),
        ("Describe a caching strategy you've used or would use for a high-traffic service.", "technical", "medium"),
        ("What are design patterns? Name 3 you've used and why.", "technical", "hard"),
    ],
    "Data Analyst": [
        ("What is the difference between a left join and an inner join in SQL?", "technical", "easy"),
        ("How do you handle missing or null values in a dataset?", "technical", "medium"),
        ("What is the difference between a mean, median, and mode? When do you use each?", "technical", "easy"),
        ("Explain what a p-value is in plain language.", "technical", "medium"),
        ("How would you detect and handle outliers in a dataset?", "technical", "medium"),
        ("What is the difference between correlation and causation?", "technical", "easy"),
        ("Describe how you would build a dashboard to track key business KPIs.", "technical", "medium"),
        ("What is A/B testing and how would you design one?", "technical", "hard"),
        ("Explain the concept of data normalization.", "technical", "medium"),
        ("How would you present complex data insights to a non-technical audience?", "behavioral", "medium"),
        ("What is ETL? Describe the steps in an ETL pipeline.", "technical", "hard"),
        ("How do you validate that your SQL query is returning the correct results?", "technical", "medium"),
        ("What's the difference between OLAP and OLTP?", "technical", "hard"),
        ("Describe a time you found a surprising insight in data.", "behavioral", "medium"),
        ("What tools have you used for data visualization and why?", "technical", "easy"),
    ],
    "Product Manager": [
        ("How do you prioritize features when you have limited engineering resources?", "behavioral", "medium"),
        ("Walk me through how you would launch a new feature end-to-end.", "technical", "hard"),
        ("How do you define success metrics for a product?", "technical", "medium"),
        ("Tell me about a product you admire and what makes it great.", "behavioral", "easy"),
        ("How do you gather and incorporate user feedback?", "technical", "medium"),
        ("Describe a time you had to say no to a stakeholder's feature request.", "behavioral", "hard"),
        ("How do you work with engineering teams to balance tech debt and new features?", "behavioral", "medium"),
        ("What's the difference between outputs and outcomes in product thinking?", "technical", "medium"),
        ("How do you handle a situation where data and user feedback conflict?", "behavioral", "hard"),
        ("Walk me through how you would define an MVP for a new product idea.", "technical", "medium"),
        ("How do you use A/B testing in your product decisions?", "technical", "medium"),
        ("Describe your approach to roadmap planning.", "technical", "hard"),
        ("How do you align cross-functional teams around a product vision?", "behavioral", "hard"),
        ("Tell me about a product failure and what you learned from it.", "behavioral", "hard"),
        ("What frameworks do you use to evaluate product opportunities?", "technical", "medium"),
    ],
    "Data Scientist": [
        ("Explain the bias-variance tradeoff.", "technical", "medium"),
        ("What is the difference between supervised and unsupervised learning?", "technical", "easy"),
        ("How do you handle class imbalance in a classification problem?", "technical", "hard"),
        ("What is cross-validation and why is it important?", "technical", "medium"),
        ("Explain the difference between L1 and L2 regularization.", "technical", "hard"),
        ("What is feature engineering and why does it matter?", "technical", "medium"),
        ("How would you explain a machine learning model's output to a business stakeholder?", "behavioral", "medium"),
        ("What is the difference between precision and recall?", "technical", "medium"),
        ("When would you use a random forest over a linear regression model?", "technical", "hard"),
        ("How do you detect and mitigate data leakage?", "technical", "hard"),
        ("What is a confusion matrix and how do you interpret it?", "technical", "easy"),
        ("Describe the steps you take from raw data to a deployed model.", "technical", "hard"),
        ("How do you evaluate whether a model is ready for production?", "technical", "hard"),
        ("What is PCA and when would you use it?", "technical", "hard"),
        ("Tell me about a machine learning project you're proud of.", "behavioral", "medium"),
    ],
    "DevOps Engineer": [
        ("What is Infrastructure as Code and which tools have you used?", "technical", "medium"),
        ("Explain the difference between blue-green deployment and canary deployment.", "technical", "hard"),
        ("What is Kubernetes and what problem does it solve?", "technical", "medium"),
        ("How do you monitor application health in production?", "technical", "medium"),
        ("Describe how you would set up a CI/CD pipeline from scratch.", "technical", "hard"),
        ("What is the difference between horizontal and vertical scaling?", "technical", "easy"),
        ("How do you handle secrets management in a cloud environment?", "technical", "hard"),
        ("What is a service mesh and when would you use one?", "technical", "hard"),
        ("Explain what happens during a Kubernetes rolling update.", "technical", "hard"),
        ("How do you approach incident response when a production system goes down?", "behavioral", "hard"),
        ("What is the 12-factor app methodology?", "technical", "medium"),
        ("How do you implement zero-downtime deployments?", "technical", "hard"),
        ("What is the difference between Docker and a virtual machine?", "technical", "easy"),
        ("How do you manage log aggregation at scale?", "technical", "medium"),
        ("Describe your experience with cloud providers (AWS/GCP/Azure).", "technical", "medium"),
    ],
    "Frontend Developer": [
        ("What is the difference between var, let, and const in JavaScript?", "technical", "easy"),
        ("Explain the browser's critical rendering path.", "technical", "hard"),
        ("What is the difference between CSS Grid and Flexbox? When do you use each?", "technical", "medium"),
        ("What are React Hooks and why were they introduced?", "technical", "medium"),
        ("Explain what happens when you type a URL in a browser and hit Enter.", "technical", "hard"),
        ("How do you optimize a slow-loading web application?", "technical", "hard"),
        ("What is the difference between server-side rendering and client-side rendering?", "technical", "medium"),
        ("Explain event delegation in JavaScript.", "technical", "medium"),
        ("What is accessibility (a11y) and how do you implement it?", "technical", "medium"),
        ("What is the virtual DOM and how does React use it?", "technical", "medium"),
        ("How do you handle state management in a large React application?", "technical", "hard"),
        ("What is CORS and how do you deal with it?", "technical", "medium"),
        ("Explain the concept of code splitting in webpack.", "technical", "hard"),
        ("What are Web Workers and when would you use them?", "technical", "hard"),
        ("How do you write maintainable CSS at scale?", "technical", "medium"),
    ],
    "Backend Developer": [
        ("What is the difference between a monolith and microservices architecture?", "technical", "medium"),
        ("Explain the concept of database indexing and when to use it.", "technical", "medium"),
        ("What is an ORM? What are its advantages and disadvantages?", "technical", "medium"),
        ("How do you handle authentication and session management in a web API?", "technical", "hard"),
        ("What is message queuing and when would you use it?", "technical", "hard"),
        ("Explain the N+1 query problem and how to fix it.", "technical", "hard"),
        ("What is database connection pooling and why is it important?", "technical", "medium"),
        ("How do you design an API for backward compatibility?", "technical", "hard"),
        ("What is rate limiting and how would you implement it?", "technical", "medium"),
        ("Explain the difference between synchronous and asynchronous processing.", "technical", "medium"),
        ("What is a race condition? How do you prevent it?", "technical", "hard"),
        ("How would you handle a database migration in a live production system?", "technical", "hard"),
        ("What is GraphQL and how does it differ from REST?", "technical", "medium"),
        ("Describe how you would implement full-text search.", "technical", "hard"),
        ("What logging and observability practices do you follow?", "technical", "medium"),
    ],
    
}
# Expand to guaranteed minimum counts in DB itself
HR_QUESTIONS = expand_hr_questions(HR_QUESTIONS)

for role_name in list(ROLE_QUESTIONS.keys()):
    ROLE_QUESTIONS[role_name] = expand_role_questions(role_name, ROLE_QUESTIONS[role_name]) 
    
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # HR Questions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hr_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL DEFAULT 'behavioral',
            difficulty TEXT NOT NULL DEFAULT 'medium'
        )
    """)

    # Role Questions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS role_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'technical',
            difficulty TEXT NOT NULL DEFAULT 'medium',
            UNIQUE(role, text)
        )
    """)

    # Sessions table (for analytics / future use)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            role TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed HR questions
    for text, qtype, diff in HR_QUESTIONS:
        cur.execute(
            "INSERT OR IGNORE INTO hr_questions (text, type, difficulty) VALUES (?, ?, ?)",
            (text, qtype, diff)
        )

    # Seed Role questions
    for role, questions in ROLE_QUESTIONS.items():
        for text, qtype, diff in questions:
            cur.execute(
                "INSERT OR IGNORE INTO role_questions (role, text, type, difficulty) VALUES (?, ?, ?, ?)",
                (role, text, qtype, diff)
            )

    conn.commit()
    conn.close()
    print(f"✅ Database initialized at {DB_PATH}")
    print(f"   HR questions: {len(HR_QUESTIONS)}")
    total_role_q = sum(len(v) for v in ROLE_QUESTIONS.values())
    print(f"   Role questions: {total_role_q} across {len(ROLE_QUESTIONS)} roles")
    print(f"   Roles: {', '.join(ROLE_QUESTIONS.keys())}")

if __name__ == "__main__":
    init_db()
