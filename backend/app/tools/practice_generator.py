import random
from typing import Dict, Any, Optional

PRACTICE_TEMPLATES_EASY = [
    {"equation": "2x + 6 = 18", "var": "x", "sol": 6, "hint": "First subtract 6 from both sides, then divide by 2."},
    {"equation": "3x - 5 = 10", "var": "x", "sol": 5, "hint": "First add 5 to both sides, then divide by 3."},
    {"equation": "4x + 8 = 24", "var": "x", "sol": 4, "hint": "First subtract 8 from both sides, then divide by 4."},
    {"equation": "5x - 10 = 15", "var": "x", "sol": 5, "hint": "First add 10 to both sides, then divide by 5."},
    {"equation": "2y + 8 = 20", "var": "y", "sol": 6, "hint": "First subtract 8 from both sides, then divide by 2."},
    {"equation": "3n + 9 = 27", "var": "n", "sol": 6, "hint": "First subtract 9 from both sides, then divide by 3."},
]

PRACTICE_TEMPLATES_MEDIUM = [
    {"equation": "4x + 6 = 2x + 16", "var": "x", "sol": 5, "hint": "Subtract 2x from both sides first, then subtract 6."},
    {"equation": "5x - 7 = 2x + 11", "var": "x", "sol": 6, "hint": "Subtract 2x from both sides, then add 7 to both sides."},
    {"equation": "3(x + 2) = 18", "var": "x", "sol": 4, "hint": "First divide both sides by 3 or expand 3*(x+2)."},
    {"equation": "2(x - 3) = 14", "var": "x", "sol": 10, "hint": "First divide both sides by 2, then add 3."},
]

PRACTICE_TEMPLATES_SCIENCE = [
    {
        "question": "If a student cycles 60 meters in 12 seconds, what is their speed in meters per second? (Formula: Speed = Distance ÷ Time)",
        "equation": "Speed = 60 / 12",
        "var": "Speed",
        "sol": 5,
        "hint": "Divide the total distance (60m) by the time taken (12s)."
    },
    {
        "question": "A force of 20 Newtons pushes a box with an acceleration of 4 m/s². What is the mass of the box? (Formula: Force = Mass × Acceleration)",
        "equation": "20 = Mass * 4",
        "var": "Mass",
        "sol": 5,
        "hint": "Divide the force (20N) by the acceleration (4 m/s²)."
    }
]

def generate_practice_question(
    topic: str = "linear_equations",
    difficulty: str = "easy",
    language: str = "en-IN"
) -> Dict[str, Any]:
    """
    Generates a structured school-level practice question for the student.

    Args:
        topic: 'linear_equations' | 'algebra' | 'science'
        difficulty: 'easy' | 'medium'
        language: Indic language code (e.g. 'en-IN', 'hi-IN')

    Returns:
        dict: {
            "topic": str,
            "difficulty": str,
            "question": str,
            "equation": str,
            "variable": str,
            "hint": str
        }
    """
    topic_clean = (topic or "linear_equations").lower()
    diff_clean = (difficulty or "easy").lower()

    if "science" in topic_clean:
        item = random.choice(PRACTICE_TEMPLATES_SCIENCE)
        return {
            "topic": "science",
            "difficulty": diff_clean,
            "question": item["question"],
            "equation": item["equation"],
            "variable": item["var"],
            "hint": item["hint"]
        }

    # Math linear equations
    pool = PRACTICE_TEMPLATES_MEDIUM if diff_clean == "medium" else PRACTICE_TEMPLATES_EASY
    item = random.choice(pool)

    # Localized framing
    if language.startswith("hi"):
        question_text = f"समीकरण हल करके {item['var']} का मान ज्ञात करें: {item['equation']}"
    elif language.startswith("ta"):
        question_text = f"சமன்பாட்டைத் தீர்த்து {item['var']} இன் மதிப்பைக் கண்டறியவும்: {item['equation']}"
    elif language.startswith("kn"):
        question_text = f"ಸಮೀಕರಣವನ್ನು ಬಿಡಿಸಿ {item['var']} ಮೌಲ್ಯವನ್ನು ಕಂಡುಹಿಡಿಯಿರಿ: {item['equation']}"
    elif language.startswith("te"):
        question_text = f"సమీకరణాన్ని పరిష్కరించి {item['var']} విలువను కనుగొనండి: {item['equation']}"
    else:
        question_text = f"Solve the linear equation for {item['var']}: {item['equation']}"

    return {
        "topic": "linear_equations",
        "difficulty": diff_clean,
        "question": question_text,
        "equation": item["equation"],
        "variable": item["var"],
        "hint": item["hint"]
    }

