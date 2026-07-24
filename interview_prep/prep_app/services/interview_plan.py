"""Modular staged interview plans shared by every interview category."""

from __future__ import annotations


BASE_SECTIONS = (
    ('introduction', 'Introduction', 1),
    ('experience', 'Experience', 1),
    ('role_skills', 'Role skills', 1),
    ('core_discussion', 'Technical / behavioural', 1),
    ('follow_ups', 'Adaptive follow-ups', 2),
    ('candidate_questions', 'Candidate questions', 1),
    ('assessment', 'Assessment', 0),
)

CATEGORY_FOCUS = {
    'behavioural': 'a behavioural example and the candidate’s personal contribution',
    'technical': 'technical decisions, correctness, and trade-offs',
    'coding': 'code reasoning, review, tests, and pseudocode without executing code',
    'system_design': 'requirements, architecture, trade-offs, reliability, and scale',
    'graduate': 'learning potential, fundamentals, projects, and motivation',
    'leadership': 'leadership judgement, influence, outcomes, and reflection',
    'product': 'customer problems, prioritisation, metrics, and cross-functional work',
    'data': 'data reasoning, quality, analysis choices, and communication',
    'mixed': 'the strongest next signal for this target role',
}


def build_interview_plan(category: str) -> list[dict]:
    focus = CATEGORY_FOCUS.get(category, CATEGORY_FOCUS['mixed'])
    return [
        {'key': key, 'label': label, 'question_limit': limit, 'focus': focus}
        for key, label, limit in BASE_SECTIONS
    ]


def section_question(section: str, category: str, target_role: str, next_focus: str = '') -> str:
    focus = next_focus or CATEGORY_FOCUS.get(category, CATEGORY_FOCUS['mixed'])
    questions = {
        'introduction': f'Tell me about yourself and why you are targeting a {target_role} role.',
        'experience': f'Which real experience best demonstrates your readiness for {target_role}, and what did you personally contribute?',
        'role_skills': f'Choose one skill that matters for {target_role}. Where have you used it, and what evidence shows your current level?',
        'core_discussion': f'Let’s explore {focus}. Walk me through a concrete example, your reasoning, and the outcome.',
        'follow_ups': f'Let’s go deeper on {focus}. What was the hardest decision, what alternatives did you consider, and what happened?',
        'candidate_questions': f'What questions would you ask the interviewer to decide whether this {target_role} opportunity is right for you?',
        'assessment': 'The interview is complete. Review your evidence-based assessment below.',
    }
    return questions.get(section, questions['follow_ups'])


def localize_question(question: str, language: str) -> str:
    if language == 'cantonese':
        return f'請用廣東話回答：{question}'
    if language == 'bilingual':
        return f'{question}\n\n你可以用英文、廣東話，或兩者回答。'
    return question
