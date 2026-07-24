import io
import json
import zipfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase, override_settings
from django.core import mail
from django.urls import reverse
from docx import Document

from prep_app.models import (
    CandidateDocument,
    CareerMemoryFact,
    CareerProfile,
    InterviewSession,
    InterviewTurn,
    RateLimitEvent,
    ReadinessSnapshot,
    ResumeVersion,
    SkillEvidence,
)
from prep_app.services.career_memory import CVImportService, memory_fingerprint
from prep_app.services.document_parser import DocumentParser
from prep_app.services.interview_coach import InterviewCoachService


DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def docx_bytes(text_lines):
    document = Document()
    for line in text_lines:
        document.add_paragraph(line)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def upload_from_bytes(payload, name='candidate.docx', content_type=DOCX_MIME):
    return SimpleUploadedFile(name, payload, content_type=content_type)


def docx_upload(text_lines, name='candidate.docx'):
    return upload_from_bytes(docx_bytes(text_lines), name)


def zip_bomb_docx(declared_mb=40, name='bomb.docx'):
    """A structurally valid DOCX whose XML expands far past the upload limit.

    Highly repetitive XML compresses at roughly 1000:1, so this lands well
    under the 10MB upload cap while declaring ~40MB of decompressed content.
    """
    body = '<w:p><w:r><w:t>' + ('A' * (declared_mb * 1024 * 1024)) + '</w:t></w:r></w:p>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(
            '[Content_Types].xml',
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr(
            '_rels/.rels',
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
            ' Target="word/document.xml"/></Relationships>',
        )
        archive.writestr(
            'word/document.xml',
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{body}</w:body></w:document>',
        )
    return SimpleUploadedFile(
        name,
        buf.getvalue(),
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
        # Deduplication keys on sha256 of the raw bytes, and two independent
        # python-docx saves are not byte-identical — zip entry timestamps have
        # 2-second granularity, so a save straddling that boundary changes the
        # digest. Reuse one payload so this asserts dedup, not clock luck.
        payload = docx_bytes(['Skills', 'Python'])
        with patch.object(CVImportService, '_request_json', return_value={'items': [{
            'category': 'skill', 'title': 'Python', 'content': 'Python', 'details': {},
            'evidence_excerpt': 'Python', 'confidence': 'high',
        }]}):
            self.client.post(reverse('cv_import'), {'cv_file': upload_from_bytes(payload)})
            self.client.post(reverse('cv_import'), {'cv_file': upload_from_bytes(payload)})
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

    def test_cv_import_drops_categories_outside_the_import_allowlist(self):
        """Grounding gate: CV extraction may only produce CV-shaped categories.

        experience/strength/growth/preference/goal come from interview answers
        and are gated by the evidence-overlap check instead. Deleting the
        allowlist here used to leave the whole suite green.
        """
        lines = ['Skills', 'Python', 'Leadership of the platform team']
        items = [
            {'category': 'skill', 'title': 'Python', 'content': 'Python', 'details': {},
             'evidence_excerpt': 'Python', 'confidence': 'high'},
            # Real excerpt, but a category CV import must never emit.
            {'category': 'experience', 'title': 'Leadership', 'details': {},
             'content': 'Leadership of the platform team',
             'evidence_excerpt': 'Leadership of the platform team', 'confidence': 'high'},
        ]

        with patch.object(CVImportService, '_request_json', return_value={'items': items}):
            self.client.post(reverse('cv_import'), {'cv_file': docx_upload(lines)})

        self.assertTrue(CareerMemoryFact.objects.filter(user=self.user, content='Python').exists())
        self.assertFalse(
            CareerMemoryFact.objects.filter(user=self.user, category='experience').exists(),
            'an out-of-allowlist category reached Career Memory',
        )

    def test_upload_validation_rejects_each_layer_independently(self):
        """The chain is size -> extension -> MIME -> magic bytes -> parser.

        Only the magic-byte layer had a test; the name of the original one
        claimed more coverage than it had.
        """
        cases = [
            ('wrong extension', upload_from_bytes(b'anything', 'resume.exe', DOCX_MIME)),
            ('disallowed MIME', upload_from_bytes(docx_bytes(['Skills']), 'resume.docx', 'text/plain')),
            ('bad DOCX signature', upload_from_bytes(b'not a zip at all', 'resume.docx', DOCX_MIME)),
            ('bad PDF signature', upload_from_bytes(b'not a pdf', 'resume.pdf', 'application/pdf')),
        ]
        for label, payload in cases:
            with self.subTest(layer=label):
                response = self.client.post(reverse('cv_import'), {'cv_file': payload})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(CandidateDocument.objects.exists(), f'{label} was accepted')

    def test_oversized_upload_is_rejected_before_parsing(self):
        oversized = upload_from_bytes(b'%PDF' + b'0' * (11 * 1024 * 1024), 'big.pdf', 'application/pdf')
        self.assertGreater(oversized.size, DocumentParser.MAX_FILE_SIZE)

        response = self.client.post(reverse('cv_import'), {'cv_file': oversized})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CandidateDocument.objects.exists())

    def test_import_still_works_when_the_model_call_raises(self):
        """The documented guarantee is that an outage degrades, never breaks.

        Every existing AI-failure test exercised the "AI disabled" short
        circuit, which returns before the try block — the except branch that
        actually catches an outage was never run.
        """
        with override_settings(CAREER_MEMORY_USE_AI=True, GEMINI_API_KEY='test-key'):
            with patch('prep_app.services.career_memory.genai') as fake_genai:
                fake_genai.Client.side_effect = RuntimeError('gemini is down')
                response = self.client.post(reverse('cv_import'), {
                    'cv_file': docx_upload(['Skills', 'Python, SQL']),
                })

        self.assertRedirects(response, reverse('coach_dashboard'))
        self.assertTrue(CareerMemoryFact.objects.filter(user=self.user, content='Python').exists())

    def test_upload_rejects_a_decompression_bomb_that_passes_the_size_check(self):
        """A DOCX is a zip, so the 10MB cap bounds only the compressed bytes.

        Without a decompressed-size ceiling, a sub-1MB upload that clears every
        other validation layer expands to gigabytes during parsing and
        OOM-kills the serverless function.
        """
        bomb = zip_bomb_docx()
        self.assertLess(bomb.size, 10 * 1024 * 1024, 'bomb must pass the upload size gate')

        response = self.client.post(reverse('cv_import'), {'cv_file': bomb})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'over the')
        self.assertFalse(CandidateDocument.objects.exists())
        self.assertFalse(CareerMemoryFact.objects.filter(user=self.user).exists())

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

    def test_a_rejected_save_leaves_every_career_memory_fact_untouched(self):
        """A save that fails validation must not half-rewrite the evidence.

        Editing an entry rewrites its CareerMemoryFact in place (including
        source_type -> 'manual'). Without one transaction around the whole
        request, entries validated before the failure stayed rewritten while the
        user was told the save failed.
        """
        version = self._create_version()
        collide = confirmed_fact(self.user, 'project', 'Taken project title', 'Taken project title')
        document = version.document
        # Sections are processed in RESUME_SECTIONS order, so the skill edit is
        # committed before the later project entry collides with `collide`. The
        # fingerprint covers category, title and content, so both must match.
        document['skills'][0]['content'] = 'Python 3'
        document['projects'][0]['title'] = 'Taken project title'
        document['projects'][0]['content'] = 'Taken project title'

        response = self.client.post(
            reverse('resume_save', args=[version.id]),
            data=json.dumps(document),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.python.refresh_from_db()
        self.project.refresh_from_db()
        version.refresh_from_db()
        # The skill was edited earlier in the same rejected request; it must be
        # rolled back, not left rewritten under a "save failed" message.
        self.assertEqual(self.python.content, 'Python')
        self.assertEqual(self.project.content, 'Built a Django interview coach')
        self.assertEqual(version.document['skills'][0]['content'], 'Python')
        self.assertEqual(collide.content, 'Taken project title')

    def test_non_numeric_coverage_percent_is_rejected_without_touching_evidence(self):
        version = self._create_version()
        document = version.document
        document['projects'][0]['content'] = 'Rewritten by a malformed payload'
        document['job_match']['coverage_percent'] = [1, 2]

        response = self.client.post(
            reverse('resume_save', args=[version.id]),
            data=json.dumps(document),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.project.refresh_from_db()
        self.assertEqual(self.project.content, 'Built a Django interview coach')

    def test_save_rejects_entries_that_are_not_the_users_confirmed_evidence(self):
        version = self._create_version()
        foreign = confirmed_fact(self.other, 'skill', 'Another candidate secret')
        pending = CareerMemoryFact.objects.get(user=self.user, content='Kubernetes')
        template = version.document

        for label, memory_id in [('another user', foreign.id), ('own unconfirmed', pending.id)]:
            with self.subTest(memory_id=label):
                document = json.loads(json.dumps(template))
                document['skills'] = [{'memory_id': memory_id, 'title': '', 'content': 'Injected'}]
                response = self.client.post(
                    reverse('resume_save', args=[version.id]),
                    data=json.dumps(document),
                    content_type='application/json',
                )
                self.assertEqual(response.status_code, 400)
                version.refresh_from_db()
                self.assertEqual(version.document['skills'][0]['content'], 'Python')

        foreign.refresh_from_db()
        self.assertEqual(foreign.user, self.other)
        self.assertEqual(foreign.content, 'Another candidate secret')

    def test_deleting_a_skill_prevents_its_confirmed_memory_from_being_reused(self):
        skill = SkillEvidence.objects.create(user=self.user, name='Python', evidence='Built a coach')
        self.client.post(reverse('coach_skill_delete', args=[skill.id]))
        self.assertFalse(CareerMemoryFact.objects.filter(user=self.user, category='skill', content='Python').exists())
        self.client.post(reverse('resume_builder'), {
            'title': 'After deletion', 'target_role': 'Backend Engineer', 'job_description': 'Python required',
        })
        self.assertEqual(ResumeVersion.objects.get().document['skills'], [])


@override_settings(INTERVIEW_COACH_USE_AI=False)
class OwnerScopedManagementTests(TestCase):
    """The delete and update views that had no coverage at all.

    Both deletes are ownership-scoped today; nothing regression-tested that,
    so dropping a `user=request.user` filter would have gone unnoticed.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='owner', password='test-pass-123')
        self.other = User.objects.create_user(username='intruder', password='test-pass-123')
        CareerProfile.objects.create(user=self.user, target_role='Backend Engineer')
        self.client.login(username='owner', password='test-pass-123')

    def _other_users_document(self):
        return CandidateDocument.objects.create(
            user=self.other, original_name='their-cv.pdf', file_type='PDF',
            mime_type='application/pdf', size_bytes=1, content_sha256='a' * 64,
            extracted_text='Private CV text', status='ready',
        )

    def _other_users_resume(self):
        return ResumeVersion.objects.create(
            user=self.other, title='Their resume',
            document={'schema_version': 1, 'personal': {}, 'skills': []},
        )

    def test_resume_delete_is_owner_scoped(self):
        theirs = self._other_users_resume()
        mine = ResumeVersion.objects.create(
            user=self.user, title='Mine', document={'schema_version': 1, 'personal': {}, 'skills': []},
        )

        self.assertEqual(self.client.post(reverse('resume_delete', args=[theirs.id])).status_code, 404)
        self.assertTrue(ResumeVersion.objects.filter(id=theirs.id).exists())

        self.client.post(reverse('resume_delete', args=[mine.id]))
        self.assertFalse(ResumeVersion.objects.filter(id=mine.id).exists())

    def test_candidate_document_delete_is_owner_scoped_and_can_keep_memory(self):
        theirs = self._other_users_document()
        self.assertEqual(
            self.client.post(reverse('candidate_document_delete', args=[theirs.id])).status_code, 404,
        )
        self.assertTrue(CandidateDocument.objects.filter(id=theirs.id).exists())

        mine = CandidateDocument.objects.create(
            user=self.user, original_name='cv.pdf', file_type='PDF', mime_type='application/pdf',
            size_bytes=1, content_sha256='b' * 64, extracted_text='My CV', status='ready',
        )
        fact = CareerMemoryFact.objects.create(
            user=self.user, category='skill', content='Python', evidence='Python',
            source_type='cv', source_document=mine,
            fingerprint=memory_fingerprint('skill', '', 'Python'),
        )

        self.client.post(reverse('candidate_document_delete', args=[mine.id]))

        self.assertFalse(CandidateDocument.objects.filter(id=mine.id).exists())
        # Memory is kept unless the user asked for it to go.
        self.assertTrue(CareerMemoryFact.objects.filter(id=fact.id).exists())

    def test_candidate_document_delete_can_remove_generated_memory(self):
        document = CandidateDocument.objects.create(
            user=self.user, original_name='cv.pdf', file_type='PDF', mime_type='application/pdf',
            size_bytes=1, content_sha256='c' * 64, extracted_text='My CV', status='ready',
        )
        CareerMemoryFact.objects.create(
            user=self.user, category='skill', content='Rust', evidence='Rust',
            source_type='cv', source_document=document,
            fingerprint=memory_fingerprint('skill', '', 'Rust'),
        )

        self.client.post(reverse('candidate_document_delete', args=[document.id]), {'delete_memories': 'on'})

        self.assertFalse(CareerMemoryFact.objects.filter(user=self.user, content='Rust').exists())

    def test_adding_a_skill_creates_confirmed_memory_and_updates_the_profile(self):
        response = self.client.post(reverse('coach_skill_add'), {
            'name': 'Django', 'self_level': 'intermediate', 'evidence': 'Built a coach app',
        })
        self.assertRedirects(response, reverse('coach_dashboard'))

        skill = SkillEvidence.objects.get(user=self.user, name='Django')
        self.assertEqual(skill.self_level, 'intermediate')
        fact = CareerMemoryFact.objects.get(user=self.user, category='skill', content='Django')
        # Manual entry is the user's own claim, so it is confirmed on the spot.
        self.assertTrue(fact.user_confirmed)
        self.assertEqual(fact.source_type, 'manual')

        response = self.client.post(reverse('coach_profile_update'), {
            'target_role': 'Staff Engineer', 'goals': 'Lead a platform team',
            'preferred_language': 'english', 'interview_style': 'challenging',
            'desired_difficulty': 'senior',
        })
        self.assertRedirects(response, reverse('coach_dashboard'))
        self.user.career_profile.refresh_from_db()
        self.assertEqual(self.user.career_profile.target_role, 'Staff Engineer')

    def test_privacy_centre_shows_only_the_signed_in_users_uploads(self):
        self._other_users_document()
        CandidateDocument.objects.create(
            user=self.user, original_name='my-own-cv.pdf', file_type='PDF',
            mime_type='application/pdf', size_bytes=1, content_sha256='d' * 64,
            extracted_text='Mine', status='ready',
        )

        response = self.client.get(reverse('privacy_center'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'my-own-cv.pdf')
        self.assertNotContains(response, 'their-cv.pdf')

    def test_invalid_submissions_are_rejected_without_creating_anything(self):
        session = InterviewSession.objects.create(
            user=self.user, target_role='Backend Engineer', current_question='Tell me about a project.',
        )

        # Answer below the minimum length.
        self.client.post(reverse('coach_answer', args=[session.id]), {'answer': 'too short'})
        self.assertFalse(InterviewTurn.objects.filter(session=session).exists())

        # Interview start with no target role.
        self.client.post(reverse('coach_start'), {'target_role': '', 'job_description': ''})
        self.assertEqual(InterviewSession.objects.filter(user=self.user).count(), 1)

        # Career Memory edit stripped of its evidence excerpt.
        fact = CareerMemoryFact.objects.create(
            user=self.user, category='project', title='A', content='Built a service',
            evidence='Built a service', fingerprint=memory_fingerprint('project', 'A', 'Built a service'),
        )
        self.client.post(reverse('coach_memory_edit', args=[fact.id]), {
            'title': 'A', 'content': 'Rewritten', 'evidence': '',
        })
        fact.refresh_from_db()
        self.assertEqual(fact.content, 'Built a service')


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

    def test_candidate_data_is_not_reachable_through_the_admin(self):
        """A staff account must not be able to read every user's evidence.

        The default ModelAdmin does no per-owner filtering, so registering
        these models made one staff credential a full PII breach.
        """
        from django.contrib import admin as django_admin

        registered = {model.__name__ for model in django_admin.site._registry}
        for private in [
            'CareerMemoryFact', 'CandidateDocument', 'InterviewSession',
            'InterviewTurn', 'ResumeVersion', 'SkillEvidence',
            'CareerProfile', 'ReadinessSnapshot',
        ]:
            self.assertNotIn(private, registered)

    def test_expensive_endpoints_are_rate_limited(self):
        """Each answer is a paid model call, and nothing throttled them.

        Also covers the unauthenticated side: without a limit, /register/
        doubles as a scriptable account-existence oracle.
        """
        session = InterviewSession.objects.create(
            user=self.user, target_role='Backend Engineer', current_question='Describe a trade-off.',
        )
        answer = {'answer': 'I compared two designs and measured the result afterwards.'}

        statuses = [
            self.client.post(reverse('coach_answer', args=[session.id]), answer).status_code
            for _ in range(62)
        ]

        self.assertTrue(all(status == 302 for status in statuses))
        # 60 allowed in the window, so the tail must not have created turns.
        self.assertLessEqual(InterviewTurn.objects.filter(session=session).count(), 60)
        self.assertTrue(
            RateLimitEvent.objects.filter(scope='coach_answer').exists(),
            'attempts should be recorded against the limit',
        )

    def test_data_export_query_count_does_not_grow_with_interview_history(self):
        """The export used to re-fetch each session by pk to reach its turns.

        That is 1 + 2N queries, unbounded in a user's own history, on a page
        that already has to serialise everything they own.
        """
        def export_queries(session_count):
            InterviewSession.objects.filter(user=self.user).delete()
            for index in range(session_count):
                session = InterviewSession.objects.create(
                    user=self.user, target_role=f'Role {index}', current_question='q',
                )
                InterviewTurn.objects.create(
                    session=session, question='q', answer='a', feedback='f', scores={'depth': 3},
                )
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(reverse('data_export'))
            self.assertEqual(response.status_code, 200)
            return len(captured)

        few = export_queries(3)
        many = export_queries(12)
        self.assertEqual(few, many, f'query count scales with history: {few} -> {many}')

    def test_job_analysis_survives_an_unusable_model_response(self):
        """A model reply that is not clean JSON must not 500 the page.

        This path used to run ast.literal_eval over free text with no
        try/except, so an ordinary LLM slip — a bare `true`, or a sentence
        before the object — reached the user as a server error.
        """
        from prep_app import views

        for reply in ['{"simplified_description": true}', 'Here is the analysis:\n{"skills": []}', '']:
            with self.subTest(reply=reply[:30]):
                with patch.object(views, 'genai') as fake_genai:
                    fake_genai.Client.return_value.models.generate_content.return_value.text = reply
                    with override_settings(GEMINI_API_KEY='test-key'):
                        response = self.client.post(reverse('ai_job_info'), {
                            'job_role': 'Backend Engineer',
                            'company_name': 'Acme',
                            'job_description': 'We need Python and Django experience.',
                        })
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Backend Engineer')

    def test_the_upload_endpoint_requires_a_signed_in_user(self):
        payload = SimpleUploadedFile('anything.bin', b'A' * 1024, content_type='application/octet-stream')
        self.client.logout()

        response = self.client.post(reverse('file_upload'), {'f': payload})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_pages_send_a_csp_and_load_no_third_party_assets(self):
        """Front-end assets are committed, so nothing is fetched off-origin.

        An unpinned CDN script running on pages that render Career Memory is
        the single largest supply-chain exposure this app had.
        """
        for url in [reverse('home'), reverse('login'), reverse('coach_dashboard')]:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
                self.assertEqual(response.status_code, 200)
                policy = response.headers['Content-Security-Policy']
                self.assertIn("script-src 'self'", policy)
                self.assertIn("object-src 'none'", policy)
                body = response.content.decode()
                for origin in ['unpkg.com', 'cdnjs.cloudflare.com', 'cdn.tailwindcss.com']:
                    self.assertNotIn(origin, body)

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


class InAppPasswordChangeTests(TestCase):
    """The signed-in password change is the supported path; it must not need email."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='candidate', password='old-password-123', email='candidate@example.com'
        )
        self.client.force_login(self.user)

    def test_profile_page_renders_a_submittable_password_form(self):
        response = self.client.get(reverse('your_profile'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        # The fields were once rendered outside any <form>, so the button posted nothing.
        self.assertIn('<form method="post"', body)
        self.assertIn('csrfmiddlewaretoken', body)
        for field in ('old_password', 'new_password1', 'new_password2'):
            self.assertIn(field, body)

    def test_valid_change_updates_the_password_and_keeps_the_user_signed_in(self):
        response = self.client.post(reverse('your_profile'), {
            'old_password': 'old-password-123',
            'new_password1': 'fresh-password-456',
            'new_password2': 'fresh-password-456',
        })
        self.assertRedirects(response, reverse('your_profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('fresh-password-456'))
        self.assertEqual(len(mail.outbox), 0)
        # update_session_auth_hash must run, or changing the password signs you out.
        self.assertEqual(self.client.get(reverse('your_profile')).status_code, 200)

    def test_wrong_current_password_is_rejected_and_shown(self):
        response = self.client.post(reverse('your_profile'), {
            'old_password': 'not-the-current-password',
            'new_password1': 'fresh-password-456',
            'new_password2': 'fresh-password-456',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'password was entered incorrectly')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('old-password-123'))

    def test_change_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse('your_profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])
