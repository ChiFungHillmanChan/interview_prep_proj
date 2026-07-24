import io
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.core import mail
from django.urls import reverse
from docx import Document

from prep_app.models import (
    CandidateDocument,
    CareerMemoryFact,
    CareerProfile,
    InterviewSession,
    ReadinessSnapshot,
    ResumeVersion,
    SkillEvidence,
)
from prep_app.services.career_memory import CVImportService, memory_fingerprint
from prep_app.services.interview_coach import InterviewCoachService


def docx_upload(text_lines, name='candidate.docx'):
    document = Document()
    for line in text_lines:
        document.add_paragraph(line)
    output = io.BytesIO()
    document.save(output)
    return SimpleUploadedFile(
        name,
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )


def confirmed_fact(user, category, content, title=''):
    return CareerMemoryFact.objects.create(
        user=user,
        category=category,
        title=title,
        content=content,
        evidence=content,
        confidence='high',
        user_confirmed=True,
        review_status='confirmed',
        source_type='manual',
        source_label='Added and confirmed by candidate',
        fingerprint=memory_fingerprint(category, title, content),
    )


@override_settings(CAREER_MEMORY_USE_AI=True)
class CVImportFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cv-owner', password='test-pass-123')
        self.other = User.objects.create_user(username='other-owner', password='test-pass-123')
        self.client.login(username='cv-owner', password='test-pass-123')

    def test_cv_import_creates_all_structured_items_as_unconfirmed_with_traceability(self):
        lines = [
            'Alex Chan', 'alex@example.com', 'Skills', 'Python',
            'Experience', 'Engineer at Acme from 2023 to 2025',
            'Projects', 'Built a scheduling service', 'Education', 'BSc Computer Science',
            'Achievements', 'Won the university project prize',
            'Certifications', 'AWS Cloud Practitioner', 'Languages', 'English, Cantonese',
        ]
        items = [
            {'category': 'personal', 'title': 'Email', 'content': 'alex@example.com', 'details': {'field': 'email'}, 'evidence_excerpt': 'alex@example.com', 'confidence': 'high'},
            {'category': 'skill', 'title': 'Python', 'content': 'Python', 'details': {}, 'evidence_excerpt': 'Python', 'confidence': 'high'},
            {'category': 'work_experience', 'title': 'Engineer at Acme', 'content': 'Engineer at Acme from 2023 to 2025', 'details': {}, 'evidence_excerpt': 'Engineer at Acme from 2023 to 2025', 'confidence': 'high'},
            {'category': 'project', 'title': 'Scheduling service', 'content': 'Built a scheduling service', 'details': {}, 'evidence_excerpt': 'Built a scheduling service', 'confidence': 'medium'},
            {'category': 'education', 'title': 'Degree', 'content': 'BSc Computer Science', 'details': {}, 'evidence_excerpt': 'BSc Computer Science', 'confidence': 'high'},
            {'category': 'achievement', 'title': 'Project prize', 'content': 'Won the university project prize', 'details': {}, 'evidence_excerpt': 'Won the university project prize', 'confidence': 'high'},
            {'category': 'certification', 'title': 'AWS', 'content': 'AWS Cloud Practitioner', 'details': {}, 'evidence_excerpt': 'AWS Cloud Practitioner', 'confidence': 'high'},
            {'category': 'language', 'title': 'Cantonese', 'content': 'Cantonese', 'details': {}, 'evidence_excerpt': 'Cantonese', 'confidence': 'high'},
            {'category': 'skill', 'title': 'Invented', 'content': 'Kubernetes', 'details': {}, 'evidence_excerpt': 'not present in source', 'confidence': 'high'},
        ]
        with patch.object(CVImportService, '_request_json', return_value={'items': items}):
            response = self.client.post(reverse('cv_import'), {'cv_file': docx_upload(lines)})

        self.assertRedirects(response, reverse('coach_dashboard'))
        self.assertEqual(CandidateDocument.objects.filter(user=self.user).count(), 1)
        memories = CareerMemoryFact.objects.filter(user=self.user)
        self.assertEqual(memories.count(), 8)
        self.assertFalse(memories.filter(user_confirmed=True).exists())
        self.assertFalse(memories.filter(content='Kubernetes').exists())
        for memory in memories:
            self.assertEqual(memory.review_status, 'pending')
            self.assertEqual(memory.source_type, 'cv')
            self.assertTrue(memory.source_document_id)
            self.assertTrue(memory.evidence)

    def test_duplicate_cv_does_not_duplicate_document_or_memory(self):
        upload = docx_upload(['Skills', 'Python'])
        with patch.object(CVImportService, '_request_json', return_value={'items': [{
            'category': 'skill', 'title': 'Python', 'content': 'Python', 'details': {},
            'evidence_excerpt': 'Python', 'confidence': 'high',
        }]}):
            self.client.post(reverse('cv_import'), {'cv_file': upload})
            self.client.post(reverse('cv_import'), {'cv_file': docx_upload(['Skills', 'Python'])})
        self.assertEqual(CandidateDocument.objects.count(), 1)
        self.assertEqual(CareerMemoryFact.objects.count(), 1)

    @override_settings(CAREER_MEMORY_USE_AI=False)
    def test_external_ai_failure_falls_back_to_conservative_section_extraction(self):
        response = self.client.post(reverse('cv_import'), {
            'cv_file': docx_upload(['Skills', 'Python, SQL', 'Languages', 'English, Cantonese']),
        })
        self.assertRedirects(response, reverse('coach_dashboard'))
        self.assertTrue(CareerMemoryFact.objects.filter(user=self.user, category='skill', content='Python').exists())
        self.assertTrue(CareerMemoryFact.objects.filter(user=self.user, category='language', content='Cantonese').exists())
        self.assertFalse(CareerMemoryFact.objects.filter(user=self.user, user_confirmed=True).exists())

    def test_upload_validation_rejects_extension_mime_and_signature_mismatches(self):
        fake_pdf = SimpleUploadedFile('candidate.pdf', b'not a pdf', content_type='application/pdf')
        response = self.client.post(reverse('cv_import'), {'cv_file': fake_pdf})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'valid PDF signature')
        self.assertFalse(CandidateDocument.objects.exists())

    def test_review_actions_are_owner_scoped_and_support_edit_reject_delete(self):
        fact = CareerMemoryFact.objects.create(
            user=self.user, category='project', content='Built a service', evidence='Built a service',
            source_type='cv', review_status='pending', fingerprint=memory_fingerprint('project', '', 'Built a service'),
        )
        other_fact = CareerMemoryFact.objects.create(
            user=self.other, category='project', content='Private project', evidence='Private project',
            fingerprint=memory_fingerprint('project', '', 'Private project'),
        )
        self.client.post(reverse('coach_memory_confirm', args=[fact.id]))
        fact.refresh_from_db()
        self.assertTrue(fact.user_confirmed)
        self.assertEqual(fact.review_status, 'confirmed')
        self.client.post(reverse('coach_memory_edit', args=[fact.id]), {
            'title': 'Scheduling service', 'content': 'Built a scheduling service', 'evidence': 'Built a service',
        })
        fact.refresh_from_db()
        self.assertEqual(fact.content, 'Built a scheduling service')
        self.client.post(reverse('coach_memory_reject', args=[fact.id]))
        fact.refresh_from_db()
        self.assertEqual(fact.review_status, 'rejected')
        self.assertEqual(self.client.post(reverse('coach_memory_delete', args=[other_fact.id])).status_code, 404)
        self.client.post(reverse('coach_memory_delete', args=[fact.id]))
        self.assertFalse(CareerMemoryFact.objects.filter(id=fact.id).exists())


@override_settings(INTERVIEW_COACH_USE_AI=False)
class TruthfulResumeFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='resume-owner', password='test-pass-123')
        self.other = User.objects.create_user(username='resume-other', password='test-pass-123')
        self.client.login(username='resume-owner', password='test-pass-123')
        self.python = confirmed_fact(self.user, 'skill', 'Python', 'Python')
        self.project = confirmed_fact(self.user, 'project', 'Built a Django interview coach', 'AceInterview')
        CareerMemoryFact.objects.create(
            user=self.user, category='skill', title='Kubernetes', content='Kubernetes', evidence='model suggestion',
            source_type='cv', review_status='pending', user_confirmed=False,
            fingerprint=memory_fingerprint('skill', 'Kubernetes', 'Kubernetes'),
        )

    def _create_version(self):
        response = self.client.post(reverse('resume_builder'), {
            'title': 'Backend resume', 'target_role': 'Backend Engineer',
            'job_description': 'We need Python, Django, and Kubernetes experience.',
        })
        version = ResumeVersion.objects.get(user=self.user)
        self.assertRedirects(response, reverse('resume_editor', args=[version.id]))
        return version

    def test_draft_uses_confirmed_claims_and_turns_missing_requirements_into_questions(self):
        version = self._create_version()
        document = version.document
        self.assertEqual(document['skills'][0]['content'], 'Python')
        self.assertNotIn('Kubernetes', json.dumps(document['skills']))
        self.assertIn('Kubernetes', document['job_match']['growth_areas'])
        self.assertTrue(any('Kubernetes' in question for question in document['job_match']['questions']))
        self.assertEqual(version.coverage_percent, 67)

    def test_live_editor_save_round_trip_persists_version_and_linked_evidence(self):
        version = self._create_version()
        document = version.document
        document['projects'][0]['content'] = 'Built and tested a Django interview coach'
        response = self.client.post(
            reverse('resume_save', args=[version.id]),
            data=json.dumps(document),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        version.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(version.document['projects'][0]['content'], 'Built and tested a Django interview coach')
        self.assertEqual(self.project.content, 'Built and tested a Django interview coach')
        self.assertIn(self.project.id, version.source_memory_ids)

    def test_resume_access_and_exports_are_owner_scoped(self):
        version = self._create_version()
        self.assertEqual(self.client.get(reverse('resume_editor', args=[version.id])).status_code, 200)
        pdf = self.client.get(reverse('resume_export_pdf', args=[version.id]))
        docx = self.client.get(reverse('resume_export_docx', args=[version.id]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertEqual(docx.status_code, 200)
        self.assertTrue(docx.content.startswith(b'PK'))
        self.client.logout()
        self.client.login(username='resume-other', password='test-pass-123')
        self.assertEqual(self.client.get(reverse('resume_editor', args=[version.id])).status_code, 404)

    def test_deleting_a_skill_prevents_its_confirmed_memory_from_being_reused(self):
        skill = SkillEvidence.objects.create(user=self.user, name='Python', evidence='Built a coach')
        self.client.post(reverse('coach_skill_delete', args=[skill.id]))
        self.assertFalse(CareerMemoryFact.objects.filter(user=self.user, category='skill', content='Python').exists())
        self.client.post(reverse('resume_builder'), {
            'title': 'After deletion', 'target_role': 'Backend Engineer', 'job_description': 'Python required',
        })
        self.assertEqual(ResumeVersion.objects.get().document['skills'], [])


@override_settings(INTERVIEW_COACH_USE_AI=False)
class StagedInterviewAndPrivacyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='interview-owner', password='test-pass-123')
        self.other = User.objects.create_user(username='private-other', password='test-pass-123')
        CareerProfile.objects.create(user=self.user, interview_style='balanced')
        self.client.login(username='interview-owner', password='test-pass-123')

    def test_staged_plan_supports_category_language_adaptive_followups_and_progress(self):
        self.client.post(reverse('coach_start'), {
            'target_role': 'Data Engineer', 'focus_areas': 'Python, leadership',
            'category': 'data', 'language': 'english_cantonese_feedback',
        })
        session = InterviewSession.objects.get(user=self.user)
        self.assertEqual(session.category, 'data')
        self.assertEqual(session.language, 'english_cantonese_feedback')
        self.assertEqual([section['key'] for section in session.plan_sections], [
            'introduction', 'experience', 'role_skills', 'core_discussion',
            'follow_ups', 'candidate_questions', 'assessment',
        ])
        assessment = {
            'feedback': 'Clear evidence with a useful result.',
            'scores': {key: 4 for key in InterviewCoachService.SCORE_KEYS},
            'assessment_confidence': 'medium', 'demonstrated_skills': [], 'memory_updates': [],
            'next_focus': 'data quality', 'next_question': 'How did you validate data quality?',
        }
        with patch.object(InterviewCoachService, 'evaluate_answer', return_value=assessment):
            for expected_section in ('experience', 'role_skills', 'core_discussion', 'follow_ups', 'follow_ups', 'candidate_questions', 'assessment'):
                self.client.post(reverse('coach_answer', args=[session.id]), {
                    'answer': 'I owned the analysis, compared alternatives, implemented the change, and measured a useful result.',
                })
                session.refresh_from_db()
                self.assertEqual(session.current_section, expected_section)
        self.assertEqual(session.status, 'completed')
        self.assertTrue(session.turns.filter(feedback__startswith='廣東話回饋').exists())
        snapshot = ReadinessSnapshot.objects.get(session=session, user=self.user)
        self.assertEqual(snapshot.evidence_answer_count, 7)
        self.assertEqual(snapshot.dimension_scores['evidence'], 4.0)
        self.assertIn('leadership', snapshot.target_role_gaps)

    def test_session_deletion_option_controls_generated_memory(self):
        session = InterviewSession.objects.create(user=self.user, target_role='Engineer', current_question='Question')
        memory = CareerMemoryFact.objects.create(
            user=self.user, category='experience', content='Session evidence', evidence='Session evidence',
            source_type='interview', source_session=session,
            fingerprint=memory_fingerprint('experience', '', 'Session evidence'),
        )
        self.client.post(reverse('coach_session_delete', args=[session.id]), {'delete_generated_memory': 'on'})
        self.assertFalse(InterviewSession.objects.filter(id=session.id).exists())
        self.assertFalse(CareerMemoryFact.objects.filter(id=memory.id).exists())

    def test_data_export_is_private_and_account_delete_requires_password(self):
        confirmed_fact(self.user, 'achievement', 'Reduced response time by 20%')
        confirmed_fact(self.other, 'achievement', 'Private other-user evidence')
        response = self.client.get(reverse('data_export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Reduced response time', response.content.decode())
        self.assertNotIn('Private other-user evidence', response.content.decode())
        self.client.post(reverse('account_delete'), {'password': 'wrong'})
        self.assertTrue(User.objects.filter(id=self.user.id).exists())
        self.client.post(reverse('account_delete'), {'password': 'test-pass-123'})
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

    def test_legacy_code_execution_route_is_disabled(self):
        response = self.client.post(reverse('run_code', args=[999]), {'code': 'import os; os.system("whoami")'})
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()['status'], 'disabled')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_a_working_reset_link_without_disclosing_accounts(self):
        self.user.email = 'candidate@example.com'
        self.user.save(update_fields=['email'])
        response = self.client.post(reverse('password_reset'), {'email': self.user.email})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/confirm/', mail.outbox[0].body)
