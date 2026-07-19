from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from prep_app.models import (
    CareerMemoryFact,
    CareerProfile,
    InterviewSession,
    InterviewTurn,
    SkillEvidence,
)
from prep_app.services.interview_coach import InterviewCoachService


@override_settings(INTERVIEW_COACH_USE_AI=False)
class InterviewCoachFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='candidate', password='test-pass-123')
        self.other_user = User.objects.create_user(username='other', password='test-pass-123')
        CareerProfile.objects.create(
            user=self.user,
            target_role='Junior Django Developer',
            preferred_language='bilingual',
            interview_style='balanced',
        )
        self.client.login(username='candidate', password='test-pass-123')

    def test_dashboard_requires_login_and_keeps_career_memory_private(self):
        SkillEvidence.objects.create(user=self.user, name='Django', evidence='Built a job preparation app')
        SkillEvidence.objects.create(user=self.other_user, name='Secret other-user skill')

        response = self.client.get(reverse('coach_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django')
        self.assertNotContains(response, 'Secret other-user skill')

        self.client.logout()
        anonymous_response = self.client.get(reverse('coach_dashboard'))
        self.assertEqual(anonymous_response.status_code, 302)
        self.assertIn(reverse('login'), anonymous_response.url)

    @patch.object(
        InterviewCoachService,
        'generate_initial_question',
        return_value='Tell me about the Django project that best shows your readiness.',
    )
    def test_starting_an_interview_uses_the_target_role_and_focus(self, _question):
        response = self.client.post(reverse('coach_start'), {
            'target_role': 'Graduate Software Engineer',
            'job_description': 'Build reliable Django services and communicate technical decisions.',
            'focus_areas': 'Django, communication, Django',
        })

        session = InterviewSession.objects.get(user=self.user)
        self.assertRedirects(response, reverse('coach_session', args=[session.id]))
        self.assertEqual(session.target_role, 'Graduate Software Engineer')
        self.assertEqual(session.focus_areas, ['Django', 'communication'])
        self.assertIn('Django project', session.current_question)

    def test_answer_updates_the_conversation_skill_evidence_and_editable_memory(self):
        skill = SkillEvidence.objects.create(
            user=self.user,
            name='Django',
            self_level='intermediate',
            evidence='Built AceInterviews',
        )
        session = InterviewSession.objects.create(
            user=self.user,
            target_role='Junior Django Developer',
            current_question='How did you design authentication in your Django project?',
        )
        assessment = {
            'feedback': 'Strong ownership and a clear result. Explain the security trade-off next.',
            'scores': {
                'technical_correctness': 4,
                'depth': 4,
                'evidence': 4,
                'problem_solving': 4,
                'communication': 4,
                'role_fit': 4,
            },
            'assessment_confidence': 'high',
            'demonstrated_skills': ['Django'],
            'memory_updates': [{
                'category': 'experience',
                'content': 'Implemented Django authentication for AceInterviews.',
                'evidence': 'Used Django authentication and protected the private views.',
                'confidence': 'high',
            }],
            'next_focus': 'security trade-offs',
            'next_question': 'Which authentication threat did you prioritise, and why?',
        }

        with patch.object(InterviewCoachService, 'evaluate_answer', return_value=assessment):
            response = self.client.post(reverse('coach_answer', args=[session.id]), {
                'answer': 'I used Django authentication and protected each private view with login checks.',
            })

        self.assertRedirects(response, reverse('coach_session', args=[session.id]))
        turn = InterviewTurn.objects.get(session=session)
        self.assertEqual(turn.question, 'How did you design authentication in your Django project?')
        self.assertEqual(turn.assessment_confidence, 'high')

        session.refresh_from_db()
        self.assertEqual(session.current_question, 'Which authentication threat did you prioritise, and why?')
        self.assertEqual(session.readiness_label, 'insufficient_evidence')

        skill.refresh_from_db()
        self.assertEqual(skill.answers_count, 1)
        self.assertEqual(skill.assessment_level, 'strong')
        self.assertEqual(skill.assessment_confidence, 'high')

        memory = CareerMemoryFact.objects.get(user=self.user)
        self.assertFalse(memory.user_confirmed)
        self.assertEqual(memory.source_session, session)

        self.client.post(reverse('coach_memory_confirm', args=[memory.id]))
        memory.refresh_from_db()
        self.assertTrue(memory.user_confirmed)

        self.client.post(reverse('coach_memory_delete', args=[memory.id]))
        self.assertFalse(CareerMemoryFact.objects.filter(id=memory.id).exists())

    def test_two_detailed_answers_produce_a_readiness_summary(self):
        session = InterviewSession.objects.create(
            user=self.user,
            target_role='Junior Django Developer',
            current_question='Describe a production problem you solved.',
        )
        assessment = {
            'feedback': 'Clear evidence with room for more technical depth.',
            'scores': {key: 4 for key in InterviewCoachService.SCORE_KEYS},
            'assessment_confidence': 'medium',
            'demonstrated_skills': [],
            'memory_updates': [],
            'next_focus': 'technical depth',
            'next_question': 'What trade-off did you make next?',
        }

        with patch.object(InterviewCoachService, 'evaluate_answer', return_value=assessment):
            for _ in range(2):
                self.client.post(reverse('coach_answer', args=[session.id]), {
                    'answer': 'I investigated the failure, compared two options, implemented the safer one, and measured the result.',
                })

        session.refresh_from_db()
        self.assertEqual(session.readiness_label, 'mostly_ready')

        finish_response = self.client.post(reverse('coach_finish', args=[session.id]))
        self.assertRedirects(finish_response, reverse('coach_session', args=[session.id]))
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        self.assertIn('Based on 2 answers', session.summary)
        self.assertIn('only the evidence shown', session.summary)

    def test_model_cannot_add_a_skill_the_candidate_did_not_name(self):
        session = InterviewSession.objects.create(
            user=self.user,
            target_role='Backend Engineer',
            current_question='Describe the deployment.',
        )
        assessment = {
            'feedback': 'The deployment explanation needs more detail.',
            'scores': {key: 3 for key in InterviewCoachService.SCORE_KEYS},
            'assessment_confidence': 'low',
            'demonstrated_skills': ['Kubernetes'],
            'memory_updates': [],
            'next_focus': 'deployment evidence',
            'next_question': 'Which deployment tool did you personally use?',
        }

        with patch.object(InterviewCoachService, 'evaluate_answer', return_value=assessment):
            self.client.post(reverse('coach_answer', args=[session.id]), {
                'answer': 'The team deployed the service, but I did not work on that part myself.',
            })

        self.assertFalse(SkillEvidence.objects.filter(user=self.user, name='Kubernetes').exists())

    def test_candidate_cannot_open_another_users_interview(self):
        other_session = InterviewSession.objects.create(
            user=self.other_user,
            target_role='Private role',
            current_question='Private question',
        )

        response = self.client.get(reverse('coach_session', args=[other_session.id]))

        self.assertEqual(response.status_code, 404)


@override_settings(INTERVIEW_COACH_USE_AI=False)
class HonestFallbackAssessmentTests(TestCase):
    def test_short_answer_does_not_claim_technical_or_role_fit_evidence(self):
        user = User.objects.create_user(username='learner')
        session = InterviewSession.objects.create(
            user=user,
            target_role='Backend Engineer',
            current_question='Explain a difficult backend decision.',
        )

        result = InterviewCoachService(use_ai=False).evaluate_answer(
            session,
            'I helped build an API but I cannot remember the implementation details.',
        )

        self.assertIsNone(result['scores']['technical_correctness'])
        self.assertIsNone(result['scores']['role_fit'])
        self.assertEqual(result['assessment_confidence'], 'low')
        self.assertIn('not enough evidence', result['feedback'].lower())
        self.assertEqual(result['memory_updates'][0]['category'], 'growth')
