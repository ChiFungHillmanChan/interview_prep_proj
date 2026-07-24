"""Authenticated CV import and privacy orchestration."""

import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .coach_forms import AccountDeleteForm, CVUploadForm
from .models import CandidateDocument, InterviewTurn
from .services.career_memory import CVImportService
from .services.document_parser import DocumentParserError
from .services.rate_limit import rate_limit


@login_required
@rate_limit(
    'cv_import', limit=20, window_seconds=3600,
    message='You have uploaded a lot of CVs recently. Please wait a moment and try again.',
)
def cv_import(request):
    form = CVUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            document, created_count, duplicate = CVImportService().import_upload(
                request.user, form.cleaned_data['cv_file']
            )
        except (ValidationError, DocumentParserError) as exc:
            form.add_error('cv_file', str(exc))
        else:
            if duplicate:
                messages.info(request, 'That CV was already imported; no duplicate memories were created.')
            else:
                messages.success(request, f'CV imported. Review {created_count} unconfirmed memory item(s).')
            return redirect('coach_dashboard')
    return render(request, 'prep_app/cv_import.html', {'form': form})


@login_required
@require_POST
def candidate_document_delete(request, document_id):
    document = get_object_or_404(CandidateDocument, id=document_id, user=request.user)
    if request.POST.get('delete_memories') == 'on':
        document.memory_facts.filter(user=request.user).delete()
    document.delete()
    messages.success(request, 'CV import deleted. No uploaded binary had been retained.')
    return redirect('coach_dashboard')


@login_required
def privacy_center(request):
    return render(request, 'prep_app/privacy_center.html', {
        'documents': request.user.candidate_documents.all(),
        'account_delete_form': AccountDeleteForm(),
    })


@login_required
def data_export(request):
    profile = getattr(request.user, 'career_profile', None)
    payload = {
        'schema_version': 1,
        'profile': {
            'username': request.user.username,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        },
        'career_profile': ({
            'target_role': profile.target_role,
            'goals': profile.goals,
            'preferred_language': profile.preferred_language,
            'interview_style': profile.interview_style,
        } if profile else None),
        'career_memory': list(request.user.career_memory.values()),
        'skills': list(request.user.skill_evidence.values()),
        # Two queries regardless of history size. This used to re-fetch each
        # session by pk just to reach its turns, costing 1 + 2N.
        'interviews': _interviews_with_turns(request.user),
        'resume_versions': list(request.user.resume_versions.values()),
        'cv_imports': list(request.user.candidate_documents.values(
            'id', 'original_name', 'file_type', 'size_bytes', 'content_sha256',
            'extracted_text', 'status', 'created_at'
        )),
    }
    response = HttpResponse(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        content_type='application/json',
    )
    response['Content-Disposition'] = 'attachment; filename="aceinterview-data.json"'
    return response


def _interviews_with_turns(user) -> list[dict]:
    """Every session with its turns attached, in two queries."""
    sessions = list(user.interview_sessions.values())
    turns_by_session: dict[int, list[dict]] = {}
    for turn in InterviewTurn.objects.filter(session__user=user).values():
        turns_by_session.setdefault(turn['session_id'], []).append(turn)
    return [{**session, 'turns': turns_by_session.get(session['id'], [])} for session in sessions]


@login_required
@require_POST
def account_delete(request):
    form = AccountDeleteForm(request.POST)
    if not form.is_valid() or not request.user.check_password(form.cleaned_data['password']):
        messages.error(request, 'Password was incorrect. Your account was not deleted.')
        return redirect('privacy_center')
    user = request.user
    logout(request)
    user.delete()
    messages.success(request, 'Your AceInterview account and private data were deleted.')
    return redirect('home')
