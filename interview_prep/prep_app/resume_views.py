"""Authenticated, persisted resume builder views."""

import json
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .coach_forms import ResumeBuilderForm
from .models import ResumeVersion
from .services.resume_builder import CareerResumeExporter, TruthfulResumeService


@login_required
def resume_builder(request):
    form = ResumeBuilderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        document, coverage = TruthfulResumeService.build_document(
            request.user,
            form.cleaned_data['target_role'],
            form.cleaned_data['job_description'],
        )
        memory_ids = sorted({
            entry['memory_id']
            for section in ('skills', 'experience', 'projects', 'education', 'achievements', 'certifications', 'languages')
            for entry in document[section]
        } | set(document.get('personal_memory_ids', {}).values()))
        version = ResumeVersion.objects.create(
            user=request.user,
            title=form.cleaned_data['title'],
            target_role=form.cleaned_data['target_role'],
            job_description=form.cleaned_data['job_description'],
            document=document,
            coverage_percent=coverage,
            source_memory_ids=memory_ids,
        )
        messages.success(request, 'Truthful draft created from confirmed Career Memory.')
        return redirect('resume_editor', version_id=version.id)
    return render(request, 'prep_app/resume_builder.html', {
        'form': form,
        'versions': request.user.resume_versions.all(),
        'confirmed_count': request.user.career_memory.filter(
            user_confirmed=True, review_status='confirmed'
        ).count(),
    })


@login_required
def resume_editor(request, version_id):
    version = get_object_or_404(ResumeVersion, id=version_id, user=request.user)
    return render(request, 'prep_app/resume_editor.html', {
        'version': version,
        'resume_document_json': json.dumps(version.document),
    })


@login_required
@require_POST
def resume_save(request, version_id):
    version = get_object_or_404(ResumeVersion, id=version_id, user=request.user)
    # normalize_saved_document rewrites the underlying CareerMemoryFact rows for
    # every edited entry, so a failure part-way through must not leave some facts
    # rewritten and the version unsaved. One transaction covers both.
    try:
        with transaction.atomic():
            raw = json.loads(request.body.decode('utf-8'))
            document = TruthfulResumeService.normalize_saved_document(request.user, raw)
            version.document = document
            version.target_role = document['target_role']
            version.coverage_percent = document['job_match']['coverage_percent']
            version.source_memory_ids = sorted({
                entry['memory_id']
                for section in ('skills', 'experience', 'projects', 'education', 'achievements', 'certifications', 'languages')
                for entry in document[section]
            } | set(document.get('personal_memory_ids', {}).values()))
            version.save(update_fields=[
                'document', 'target_role', 'coverage_percent', 'source_memory_ids', 'updated_at'
            ])
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    return JsonResponse({'ok': True, 'updated_at': version.updated_at.isoformat()})


@login_required
def resume_export_pdf(request, version_id):
    version = get_object_or_404(ResumeVersion, id=version_id, user=request.user)
    return CareerResumeExporter.pdf_response(version.document, _filename(version))


@login_required
def resume_export_docx(request, version_id):
    version = get_object_or_404(ResumeVersion, id=version_id, user=request.user)
    return CareerResumeExporter.docx_response(version.document, _filename(version))


@login_required
@require_POST
def resume_delete(request, version_id):
    version = get_object_or_404(ResumeVersion, id=version_id, user=request.user)
    version.delete()
    messages.success(request, 'Resume version deleted.')
    return redirect('resume_builder')


def _filename(version: ResumeVersion) -> str:
    safe = re.sub(r'[^A-Za-z0-9_-]+', '-', version.title).strip('-')
    return safe[:80] or 'AceInterview-resume'
