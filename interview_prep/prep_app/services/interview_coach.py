import json
import re
from typing import Any, Dict, Iterable, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import CareerMemoryFact, InterviewSession, InterviewTurn, ReadinessSnapshot, SkillEvidence
from .ai_client import request_timeout_ms
from .career_memory import memory_fingerprint
from .interview_plan import localize_question, section_question

try:
    from google import genai
except ImportError:  # pragma: no cover - exercised only in incomplete installations
    genai = None


class InterviewCoachService:
    """Adaptive interview coaching grounded in the user's own evidence."""

    SCORE_KEYS = (
        'technical_correctness',
        'depth',
        'evidence',
        'problem_solving',
        'communication',
        'role_fit',
    )

    def __init__(self, use_ai: Optional[bool] = None):
        configured = getattr(settings, 'INTERVIEW_COACH_USE_AI', True)
        self.use_ai = configured if use_ai is None else use_ai

    def generate_initial_question(
        self, user, profile, target_role: str, job_description: str,
        focus_areas: Iterable[str], language: str | None = None,
    ) -> str:
        skills = list(user.skill_evidence.values('name', 'self_level', 'evidence'))
        memory = list(user.career_memory.filter(
            user_confirmed=True, review_status='confirmed'
        ).values('category', 'content', 'confidence')[:12])
        focus_areas = list(focus_areas)

        prompt = f"""
You are an honest practice interviewer. Ask exactly one opening interview question.
Tailor it to the candidate's verified context. Never assume a skill that is not supplied.

Target role: {target_role}
Preferred language: {profile.get_preferred_language_display()}
Interview style: {profile.get_interview_style_display()}
Difficulty: {profile.get_desired_difficulty_display()}
Candidate goals: {profile.goals or 'Not provided'}
Requested focus: {json.dumps(focus_areas)}
Known skills: {json.dumps(skills, default=str)}
Career memory: {json.dumps(memory, default=str)}
Job description: {job_description[:6000] or 'Not provided'}

Return JSON only: {{"question": "..."}}
"""
        result = self._request_json(prompt)
        if result and isinstance(result.get('question'), str) and result['question'].strip():
            return localize_question(result['question'].strip()[:1500], language or profile.preferred_language)

        focus = focus_areas[0] if focus_areas else None
        if not focus and skills:
            focus = skills[0]['name']
        if focus:
            return localize_question((
                f"Tell me about a real example where you used {focus}. What was your responsibility, "
                f"what did you personally do, and what was the result for a {target_role} role?"
            ), language or profile.preferred_language)
        return localize_question((
            f"Why are you targeting a {target_role} role, and which real project or experience best "
            "demonstrates that you are ready for it?"
        ), language or profile.preferred_language)

    def evaluate_answer(self, session: InterviewSession, answer: str) -> Dict[str, Any]:
        user = session.user
        profile = getattr(user, 'career_profile', None)
        skills = list(user.skill_evidence.values(
            'name', 'self_level', 'evidence', 'assessment_level', 'assessment_confidence'
        ))
        memory = list(user.career_memory.filter(
            user_confirmed=True, review_status='confirmed'
        ).values(
            'category', 'content', 'evidence', 'confidence', 'user_confirmed'
        )[:15])
        previous_turns = list(session.turns.values('question', 'answer', 'feedback')[:8])

        prompt = f"""
You are an evidence-based interview coach. Evaluate only what this answer demonstrates.
Do not infer unmentioned skills, invent achievements, or reward keyword stuffing.
Use null when there is not enough evidence to score a dimension.

Target role: {session.target_role}
Job description: {session.job_description[:6000] or 'Not provided'}
Interview and feedback language: {session.get_language_display()}
Interview style: {profile.get_interview_style_display() if profile else 'Balanced'}
Known skills: {json.dumps(skills, default=str)}
Career memory: {json.dumps(memory, default=str)}
Previous turns: {json.dumps(previous_turns, default=str)}
Current question: {session.current_question}
Candidate answer: {answer}

Return valid JSON only with this shape:
{{
  "feedback": "Specific, candid feedback with one strength and one next improvement.",
  "scores": {{
    "technical_correctness": 1,
    "depth": 1,
    "evidence": 1,
    "problem_solving": 1,
    "communication": 1,
    "role_fit": 1
  }},
  "assessment_confidence": "low|medium|high",
  "demonstrated_skills": ["only skills actually demonstrated in the answer"],
  "memory_updates": [
    {{"category": "experience|strength|growth|preference|goal", "content": "fact", "evidence": "short quote or paraphrase", "confidence": "low|medium|high"}}
  ],
  "next_focus": "the capability to test next",
  "next_question": "one adaptive follow-up question"
}}
Each non-null score must be an integer from 1 to 5. Keep memory updates factual and grounded in the answer.
"""
        result = self._request_json(prompt)
        return self._normalize_result(result) if result else self._fallback_evaluation(session, answer, skills)

    def record_answer(self, session: InterviewSession, answer: str) -> InterviewTurn:
        # The model call happens before the transaction opens. Production reaches
        # Postgres through a transaction-mode pooler, so an open transaction
        # holds a backend connection \u2014 and a slow Gemini response would hold it
        # for the whole round trip.
        result = self.evaluate_answer(session, answer)
        return self._persist_answer(session, answer, result)

    @transaction.atomic
    def _persist_answer(self, session: InterviewSession, answer: str, result: Dict[str, Any]) -> InterviewTurn:
        if session.language in {'cantonese', 'english_cantonese_feedback'} and not re.search(r'[\u3400-\u9fff]', result['feedback']):
            result['feedback'] = f"廣東話回饋：{result['feedback']}"
        turn = InterviewTurn.objects.create(
            session=session,
            section=session.current_section,
            question=session.current_question,
            answer=answer.strip(),
            feedback=result['feedback'],
            scores=result['scores'],
            assessment_confidence=result['assessment_confidence'],
            demonstrated_skills=result['demonstrated_skills'],
            next_focus=result['next_focus'],
        )

        self._store_memory_updates(session, answer, result['memory_updates'])
        self._update_skill_assessments(session.user, answer, result)

        next_section, next_index = self._next_section(session)
        session.current_section = next_section
        session.current_section_index = next_index
        if not session.plan_sections:
            session.current_question = result['next_question']
        elif next_section == 'assessment':
            session.current_question = section_question('assessment', session.category, session.target_role)
        elif next_section == 'follow_ups':
            session.current_question = localize_question(result['next_question'], session.language)
        else:
            session.current_question = localize_question(
                section_question(next_section, session.category, session.target_role, result['next_focus']),
                session.language,
            )
        session.readiness_label = self._calculate_readiness(session)
        session.save(update_fields=[
            'current_question', 'current_section', 'current_section_index',
            'readiness_label', 'updated_at',
        ])
        if next_section == 'assessment':
            self.complete_session(session)
        return turn

    def complete_session(self, session: InterviewSession) -> InterviewSession:
        session.status = 'completed'
        session.completed_at = timezone.now()
        session.readiness_label = self._calculate_readiness(session)
        turn_count = session.turns.count()
        if turn_count < 2:
            session.summary = (
                "There is not enough interview evidence for a reliable level assessment yet. "
                "Complete at least two detailed answers so the coach can identify a pattern."
            )
        else:
            strongest, weakest = self._strongest_and_weakest_dimensions(session)
            session.summary = (
                f"Based on {turn_count} answers, your strongest demonstrated area is {strongest}. "
                f"Your next practice priority is {weakest}. This assessment reflects only the "
                "evidence shown in this session."
            )
        session.save(update_fields=['status', 'completed_at', 'readiness_label', 'summary', 'updated_at'])
        ReadinessSnapshot.objects.update_or_create(
            user=session.user,
            session=session,
            defaults={
                'readiness_label': session.readiness_label,
                'dimension_scores': self._dimension_averages(session),
                'target_role_gaps': self._target_role_gaps(session),
                'evidence_answer_count': turn_count,
            },
        )
        return session

    def _request_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.use_ai or genai is None:
            return None
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            return None
        try:
            # Without an explicit timeout the SDK passes timeout=None straight
            # through to httpx, which disables every deadline. A hung call would
            # then run to the platform's function limit and the caller would
            # never reach the deterministic fallback below.
            client = genai.Client(api_key=api_key, http_options={'timeout': request_timeout_ms()})
            response = client.models.generate_content(
                model=getattr(settings, 'INTERVIEW_COACH_MODEL', 'gemini-2.5-flash-lite'),
                contents=prompt,
                config={'temperature': 0.2, 'response_mime_type': 'application/json'},
            )
            text = response.text.strip().replace('```json', '').replace('```', '').strip()
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            # The practice flow remains usable if the external model is unavailable.
            return None

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        raw_scores = result.get('scores') if isinstance(result.get('scores'), dict) else {}
        scores = {}
        for key in self.SCORE_KEYS:
            value = raw_scores.get(key)
            if value is None:
                scores[key] = None
                continue
            try:
                numeric = int(value)
            except (TypeError, ValueError):
                scores[key] = None
            else:
                scores[key] = min(5, max(1, numeric))

        confidence = result.get('assessment_confidence', 'low')
        if confidence not in {'low', 'medium', 'high'}:
            confidence = 'low'

        memory_updates = []
        raw_updates = result.get('memory_updates')
        if not isinstance(raw_updates, list):
            raw_updates = []
        for update in raw_updates:
            if not isinstance(update, dict) or not str(update.get('content', '')).strip():
                continue
            category = update.get('category', 'experience')
            if category not in {'experience', 'strength', 'growth', 'preference', 'goal'}:
                category = 'experience'
            memory_updates.append({
                'category': category,
                'content': str(update['content']).strip()[:1000],
                'evidence': str(update.get('evidence', '')).strip()[:1000],
                'confidence': update.get('confidence') if update.get('confidence') in {'low', 'medium', 'high'} else 'low',
            })

        raw_demonstrated = result.get('demonstrated_skills')
        if not isinstance(raw_demonstrated, list):
            raw_demonstrated = []
        demonstrated = [
            str(skill).strip()[:100]
            for skill in raw_demonstrated
            if str(skill).strip()
        ][:8]

        return {
            'feedback': str(result.get('feedback') or 'Not enough evidence for detailed feedback yet.').strip()[:4000],
            'scores': scores,
            'assessment_confidence': confidence,
            'demonstrated_skills': list(dict.fromkeys(demonstrated)),
            'memory_updates': memory_updates[:5],
            'next_focus': str(result.get('next_focus') or 'a concrete example').strip()[:200],
            'next_question': str(result.get('next_question') or 'Can you give a more specific example and explain the result?').strip()[:1500],
        }

    def _fallback_evaluation(self, session, answer: str, skills) -> Dict[str, Any]:
        words = answer.split()
        lower = answer.lower()
        has_result = bool(re.search(r'\b(result|outcome|improved|reduced|increased|saved|achieved)\b', lower))
        has_reasoning = bool(re.search(r'\b(because|trade[- ]?off|alternative|decided|reason)\b', lower))
        has_specifics = bool(re.search(r'\d|%|\b(users?|seconds?|hours?|days?|weeks?)\b', lower))
        star_markers = sum(marker in lower for marker in ('situation', 'task', 'action', 'result'))

        demonstrated = [skill['name'] for skill in skills if skill['name'].lower() in lower]
        enough_detail = len(words) >= 60
        scores = {
            'technical_correctness': None,
            'depth': 4 if len(words) >= 140 else 3 if enough_detail else 2,
            'evidence': 4 if has_result and has_specifics else 3 if has_result else 2,
            'problem_solving': 4 if has_reasoning else 2,
            'communication': 4 if 60 <= len(words) <= 260 or star_markers >= 2 else 3 if len(words) >= 30 else 2,
            'role_fit': None,
        }
        confidence = 'medium' if enough_detail and (has_result or has_reasoning) else 'low'

        if not enough_detail:
            feedback = (
                "You gave a relevant starting point, but there is not enough evidence to judge your level reliably. "
                "Add what you personally did, why you chose that approach, and a measurable or observable result."
            )
        elif not has_result:
            feedback = (
                "Your explanation has useful detail, but the outcome is still unclear. State what changed because "
                "of your work and separate your personal contribution from the team's work."
            )
        else:
            feedback = (
                "This answer includes concrete evidence and a visible outcome. To make it stronger, explain one "
                "trade-off or alternative you considered so the interviewer can see the depth of your judgement."
            )

        memory_updates = []
        if enough_detail:
            memory_updates.append({
                'category': 'experience',
                'content': f"Described experience relevant to {session.target_role}: {' '.join(words[:35])}",
                'evidence': answer[:500],
                'confidence': confidence,
            })
        else:
            memory_updates.append({
                'category': 'growth',
                'content': 'Needs to support interview answers with clearer personal actions and outcomes.',
                'evidence': answer[:300],
                'confidence': 'low',
            })

        focus = demonstrated[0] if demonstrated else 'decision-making and measurable impact'
        return self._normalize_result({
            'feedback': feedback,
            'scores': scores,
            'assessment_confidence': confidence,
            'demonstrated_skills': demonstrated,
            'memory_updates': memory_updates,
            'next_focus': focus,
            'next_question': (
                f"Let’s go deeper on {focus}. What was the hardest decision you made, which alternatives did "
                "you consider, and how did you know your choice worked?"
            ),
        })

    def _store_memory_updates(self, session, answer: str, updates) -> None:
        for update in updates:
            evidence = update['evidence'].strip()
            answer_words = set(re.findall(r'[a-z0-9]+', answer.casefold()))
            evidence_words = set(re.findall(r'[a-z0-9]+', evidence.casefold()))
            overlap = len(answer_words & evidence_words) / max(1, len(evidence_words))
            if not evidence or overlap < 0.55:
                continue
            CareerMemoryFact.objects.get_or_create(
                user=session.user,
                fingerprint=memory_fingerprint(update['category'], '', update['content']),
                defaults={
                    'category': update['category'],
                    'content': update['content'],
                    'evidence': answer.strip()[:1000],
                    'confidence': update['confidence'],
                    'user_confirmed': False,
                    'review_status': 'pending',
                    'source_type': 'interview',
                    'source_label': f'Interview for {session.target_role}',
                    'source_session': session,
                },
            )

    def _update_skill_assessments(self, user, answer: str, result) -> None:
        scored = [value for value in result['scores'].values() if isinstance(value, int)]
        if not scored:
            return
        answer_score = sum(scored) / len(scored)
        answer_lower = answer.lower()
        for skill_name in result['demonstrated_skills']:
            # A model label alone is not evidence. The candidate must have actually
            # named the skill in the answer before it can affect Career Memory.
            if skill_name.lower() not in answer_lower:
                continue
            skill, _ = SkillEvidence.objects.get_or_create(
                user=user,
                name=skill_name,
                defaults={'self_level': 'unknown'},
            )
            previous_total = (skill.average_score or 0) * skill.answers_count
            skill.answers_count += 1
            skill.average_score = round((previous_total + answer_score) / skill.answers_count, 2)
            skill.assessment_level = (
                'strong' if skill.average_score >= 4 else
                'working' if skill.average_score >= 2.8 else
                'developing'
            )
            skill.assessment_confidence = result['assessment_confidence']
            skill.save(update_fields=[
                'answers_count', 'average_score', 'assessment_level',
                'assessment_confidence', 'updated_at'
            ])

    def _calculate_readiness(self, session) -> str:
        turns = list(session.turns.values_list('scores', flat=True))
        if len(turns) < 2:
            return 'insufficient_evidence'
        values = [
            score
            for scores in turns
            for score in scores.values()
            if isinstance(score, (int, float))
        ]
        if len(values) < 6:
            return 'insufficient_evidence'
        average = sum(values) / len(values)
        if average >= 4.2:
            return 'ready'
        if average >= 3.3:
            return 'mostly_ready'
        return 'building'

    def _strongest_and_weakest_dimensions(self, session):
        buckets = {key: [] for key in self.SCORE_KEYS}
        for scores in session.turns.values_list('scores', flat=True):
            for key, value in scores.items():
                if key in buckets and isinstance(value, (int, float)):
                    buckets[key].append(value)
        averages = {key: sum(values) / len(values) for key, values in buckets.items() if values}
        if not averages:
            return 'not enough evidence', 'providing specific evidence'
        strongest = max(averages, key=averages.get).replace('_', ' ')
        weakest = min(averages, key=averages.get).replace('_', ' ')
        return strongest, weakest

    def _next_section(self, session: InterviewSession) -> tuple[str, int]:
        plan = session.plan_sections or []
        if not plan:
            return session.current_section, session.current_section_index
        current_index = min(session.current_section_index, len(plan) - 1)
        current = plan[current_index]
        answered_in_section = session.turns.filter(section=current['key']).count()
        if answered_in_section < int(current.get('question_limit', 1)):
            return current['key'], current_index
        next_index = min(current_index + 1, len(plan) - 1)
        return plan[next_index]['key'], next_index

    def _dimension_averages(self, session: InterviewSession) -> Dict[str, float | None]:
        buckets = {key: [] for key in self.SCORE_KEYS}
        for scores in session.turns.values_list('scores', flat=True):
            for key in self.SCORE_KEYS:
                value = scores.get(key) if isinstance(scores, dict) else None
                if isinstance(value, (int, float)):
                    buckets[key].append(value)
        return {
            key: round(sum(values) / len(values), 2) if values else None
            for key, values in buckets.items()
        }

    def _target_role_gaps(self, session: InterviewSession) -> list[str]:
        requirements = [area for area in session.focus_areas if str(area).strip()]
        evidenced = ' '.join(
            session.user.career_memory.filter(user_confirmed=True, review_status='confirmed')
            .values_list('content', flat=True)
        ).casefold()
        return [requirement for requirement in requirements if str(requirement).casefold() not in evidenced][:12]
