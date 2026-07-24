"""Canonical Career Memory import and normalization boundary.

Every durable fact has this contract::

    {
        "schema_version": 1,
        "category": "personal|skill|work_experience|project|education|achievement|certification|language|...",
        "title": "short user-facing label",
        "content": "one evidence-backed claim",
        "details": {},
        "evidence_excerpt": "text present in the user-provided source",
        "source": {"type": "cv|interview|manual", "label": "..."},
        "confidence": "low|medium|high",
        "review_status": "pending|confirmed|rejected",
    }

Model output is accepted only when its evidence excerpt is present in the source.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Iterable

from django.conf import settings
from django.db import transaction

from ..models import CandidateDocument, CareerMemoryFact
from .ai_client import request_timeout_ms
from .document_parser import DocumentParser

try:
    from google import genai
except ImportError:  # pragma: no cover - depends on optional external SDK
    genai = None


MEMORY_SCHEMA_VERSION = 1
IMPORT_CATEGORIES = {
    'personal', 'skill', 'work_experience', 'project', 'education',
    'achievement', 'certification', 'language',
}


def memory_fingerprint(category: str, title: str, content: str) -> str:
    normalized = '|'.join(
        re.sub(r'\s+', ' ', value).strip().casefold()
        for value in (category, title, content)
    )
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


class CVImportService:
    """Parse a CV and create reviewable, evidence-backed Career Memory facts."""

    def __init__(self, use_ai: bool | None = None):
        configured = getattr(settings, 'CAREER_MEMORY_USE_AI', True)
        self.use_ai = configured if use_ai is None else use_ai

    def import_upload(self, user, uploaded_file) -> tuple[CandidateDocument, int, bool]:
        DocumentParser.validate_file(uploaded_file)
        raw_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        digest = hashlib.sha256(raw_bytes).hexdigest()
        existing = CandidateDocument.objects.filter(user=user, content_sha256=digest).first()
        if existing:
            return existing, 0, True

        extracted_text, file_type = DocumentParser.parse_file(uploaded_file)
        # Parsing and the model call both happen before the transaction opens:
        # production reaches Postgres through a transaction-mode pooler, so an
        # open transaction holds a backend connection for its whole duration.
        raw_items = self._extract_structured(extracted_text)
        normalized_items = self.normalize_items(raw_items, extracted_text)
        return self._persist_import(
            user, uploaded_file, digest, extracted_text, file_type, normalized_items
        )

    @transaction.atomic
    def _persist_import(
        self, user, uploaded_file, digest: str, extracted_text: str,
        file_type: str, normalized_items: list[dict[str, Any]],
    ) -> tuple[CandidateDocument, int, bool]:
        document, created = CandidateDocument.objects.get_or_create(
            user=user,
            content_sha256=digest,
            defaults={
                'original_name': uploaded_file.name[:255],
                'file_type': file_type,
                'mime_type': (getattr(uploaded_file, 'content_type', '') or '')[:120],
                'size_bytes': uploaded_file.size,
                'extracted_text': extracted_text,
                'status': 'processing',
            },
        )
        if not created:
            # A concurrent upload of the same file won the race.
            return document, 0, True

        created_count = 0
        for item in normalized_items:
            _, created = CareerMemoryFact.objects.get_or_create(
                user=user,
                fingerprint=item['fingerprint'],
                defaults={
                    'category': item['category'],
                    'title': item['title'],
                    'content': item['content'],
                    'details': item['details'],
                    'evidence': item['evidence_excerpt'],
                    'confidence': item['confidence'],
                    'user_confirmed': False,
                    'review_status': 'pending',
                    'source_type': 'cv',
                    'source_label': document.original_name,
                    'source_document': document,
                },
            )
            created_count += int(created)

        document.status = 'ready'
        document.save(update_fields=['status'])
        return document, created_count, False

    def _extract_structured(self, source_text: str) -> list[dict[str, Any]]:
        prompt = f"""
Extract candidate facts from this CV. Do not infer or improve anything. Each item must
include an exact evidence_excerpt copied from the CV. Return JSON only:
{{"items":[{{"category":"personal|skill|work_experience|project|education|achievement|certification|language","title":"","content":"","details":{{}},"evidence_excerpt":"","confidence":"low|medium|high"}}]}}
CV:\n{source_text[:50000]}
"""
        ai_result = self._request_json(prompt)
        if ai_result and isinstance(ai_result.get('items'), list):
            return ai_result['items']
        return self._fallback_extract(source_text)

    def _request_json(self, prompt: str) -> dict[str, Any] | None:
        if not self.use_ai or genai is None:
            return None
        api_key = getattr(settings, 'GEMINI_API_KEY', '')
        if not api_key:
            return None
        try:
            # See interview_coach._request_timeout_ms: the SDK otherwise passes
            # timeout=None to httpx, which disables every deadline.
            client = genai.Client(api_key=api_key, http_options={'timeout': request_timeout_ms()})
            response = client.models.generate_content(
                model=getattr(settings, 'INTERVIEW_COACH_MODEL', 'gemini-2.5-flash-lite'),
                contents=prompt,
                config={'temperature': 0, 'response_mime_type': 'application/json'},
            )
            parsed = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    @classmethod
    def normalize_items(cls, items: Iterable[Any], source_text: str) -> list[dict[str, Any]]:
        normalized = []
        seen = set()
        source_folded = re.sub(r'\s+', ' ', source_text).casefold()
        for raw in items:
            if not isinstance(raw, dict):
                continue
            category = str(raw.get('category', '')).strip()
            title = re.sub(r'\s+', ' ', str(raw.get('title', ''))).strip()[:250]
            content = re.sub(r'\s+', ' ', str(raw.get('content', ''))).strip()[:2000]
            evidence = re.sub(r'\s+', ' ', str(raw.get('evidence_excerpt', ''))).strip()[:1000]
            if category not in IMPORT_CATEGORIES or not content or not evidence:
                continue
            if evidence.casefold() not in source_folded:
                continue
            details = raw.get('details') if isinstance(raw.get('details'), dict) else {}
            details = {
                str(key)[:80]: str(value).strip()[:500]
                for key, value in list(details.items())[:12]
                if str(value).strip()
            }
            confidence = raw.get('confidence')
            if confidence not in {'low', 'medium', 'high'}:
                confidence = 'low'
            fingerprint = memory_fingerprint(category, title, content)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            normalized.append({
                'schema_version': MEMORY_SCHEMA_VERSION,
                'category': category,
                'title': title,
                'content': content,
                'details': details,
                'evidence_excerpt': evidence,
                'confidence': confidence,
                'fingerprint': fingerprint,
            })
        return normalized[:150]

    @staticmethod
    def _fallback_extract(source_text: str) -> list[dict[str, Any]]:
        """Conservative local extraction used when the model is unavailable."""
        items: list[dict[str, Any]] = []
        lines = [re.sub(r'\s+', ' ', line).strip() for line in source_text.splitlines() if line.strip()]
        if not lines:
            lines = [part.strip() for part in re.split(r'(?<=[.!?])\s+', source_text) if part.strip()]

        email = re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', source_text)
        phone = re.search(r'(?<!\w)(?:\+?\d[\d ()-]{7,}\d)', source_text)
        for label, match in [('Email', email), ('Phone', phone)]:
            if match:
                excerpt = match.group(0).strip()
                items.append({'category': 'personal', 'title': label, 'content': excerpt,
                              'details': {'field': label.casefold()}, 'evidence_excerpt': excerpt,
                              'confidence': 'high'})

        section_map = {
            'skills': 'skill', 'technical skills': 'skill',
            'experience': 'work_experience', 'work experience': 'work_experience',
            'projects': 'project', 'education': 'education',
            'achievements': 'achievement', 'awards': 'achievement',
            'certifications': 'certification', 'certificates': 'certification',
            'languages': 'language',
        }
        current_category = None
        for line in lines:
            header = line.strip(':').casefold()
            if header in section_map:
                current_category = section_map[header]
                continue
            if not current_category or len(line) < 2:
                continue
            if current_category in {'skill', 'language', 'certification'}:
                values = [value.strip(' •-') for value in re.split(r'[,|•]', line) if value.strip(' •-')]
            else:
                values = [line.strip(' •-')]
            for value in values[:20]:
                if 1 < len(value) <= 500:
                    items.append({
                        'category': current_category,
                        'title': value[:100],
                        'content': value,
                        'details': {},
                        'evidence_excerpt': value,
                        'confidence': 'medium',
                    })
        return items
