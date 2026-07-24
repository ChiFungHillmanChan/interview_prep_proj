from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from .coach_forms import (
    CareerMemoryEditForm,
    CareerProfileForm,
    InterviewAnswerForm,
    SessionDeleteForm,
    SkillEvidenceForm,
    StartInterviewForm,
)
from .models import CareerMemoryFact, CareerProfile, InterviewSession, SkillEvidence
from .services.interview_coach import InterviewCoachService
from .services.interview_plan import build_interview_plan
from .services.career_memory import memory_fingerprint


@login_required
def coach_dashboard(request):
    profile, _ = CareerProfile.objects.get_or_create(user=request.user)
    skills = request.user.skill_evidence.all()
    memory = request.user.career_memory.select_related('source_session')[:12]
    sessions = request.user.interview_sessions.prefetch_related('turns')[:8]
    snapshots = list(request.user.readiness_history.all())
    dimension_trends = {}
    for snapshot in snapshots:
        for dimension, score in snapshot.dimension_scores.items():
            if score is not None:
                dimension_trends.setdefault(dimension, []).append(score)

    context = {
        'profile': profile,
        'profile_form': CareerProfileForm(instance=profile),
        'skill_form': SkillEvidenceForm(),
        'start_form': StartInterviewForm(initial={'target_role': profile.target_role}),
        'skills': skills,
        'memory': memory,
        'memory_count': request.user.career_memory.count(),
        'sessions': sessions,
        'completed_sessions': request.user.interview_sessions.filter(status='completed').count(),
        'assessed_skills': skills.exclude(assessment_level='not_assessed').count(),
        'pending_memory_count': request.user.career_memory.filter(review_status='pending').count(),
        'documents': request.user.candidate_documents.all()[:8],
        'resume_versions': request.user.resume_versions.all()[:8],
        'readiness_history': snapshots,
        'dimension_trends': dimension_trends,
        'target_role_gaps': snapshots[-1].target_role_gaps if snapshots else [],
    }
    return render(request, 'prep_app/coach_dashboard.html', context)


@login_required
@require_POST
def coach_profile_update(request):
    profile, _ = CareerProfile.objects.get_or_create(user=request.user)
    form = CareerProfileForm(request.POST, instance=profile)
    if form.is_valid():
        form.save()
        messages.success(request, 'Your coaching preferences have been updated.')
    else:
        messages.error(request, 'Please correct the profile details and try again.')
    return redirect('coach_dashboard')


@login_required
@require_POST
def coach_skill_add(request):
    form = SkillEvidenceForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data['name']
        # unique_skill_per_user makes the filter-then-save below a race: a
        # double-clicked submit had both requests see no existing row and the
        # loser raised IntegrityError, which nothing caught.
        try:
            with transaction.atomic():
                skill = request.user.skill_evidence.filter(name__iexact=name).first()
                if skill is None:
                    skill = SkillEvidence(user=request.user, name=name)
                skill.self_level = form.cleaned_data['self_level']
                skill.evidence = form.cleaned_data['evidence']
                skill.save()
        except IntegrityError:
            skill = request.user.skill_evidence.get(name=name)
            skill.self_level = form.cleaned_data['self_level']
            skill.evidence = form.cleaned_data['evidence']
            skill.save()
        if skill.evidence:
            fingerprint = memory_fingerprint('skill', skill.name, skill.name)
            request.user.career_memory.update_or_create(
                fingerprint=fingerprint,
                defaults={
                    'category': 'skill', 'title': skill.name, 'content': skill.name,
                    'evidence': skill.evidence, 'confidence': 'high',
                    'user_confirmed': True, 'review_status': 'confirmed',
                    'source_type': 'manual', 'source_label': 'Added and confirmed by candidate',
                },
            )
        messages.success(request, f'{skill.name} has been added to your Career Memory.')
    else:
        messages.error(request, 'Please provide a valid skill name and level.')
    return redirect('coach_dashboard')


@login_required
@require_POST
def coach_skill_delete(request, skill_id):
    skill = get_object_or_404(SkillEvidence, id=skill_id, user=request.user)
    request.user.career_memory.filter(category='skill', content__iexact=skill.name).delete()
    skill.delete()
    messages.success(request, 'The skill has been removed from your Career Memory.')
    return redirect('coach_dashboard')


@login_required
@require_POST
def coach_memory_confirm(request, fact_id):
    fact = get_object_or_404(CareerMemoryFact, id=fact_id, user=request.user)
    fact.user_confirmed = not fact.user_confirmed
    fact.review_status = 'confirmed' if fact.user_confirmed else 'pending'
    fact.save(update_fields=['user_confirmed', 'review_status', 'updated_at'])
    messages.success(request, 'Career Memory confirmation updated.')
    return redirect(_safe_return_url(request))


@login_required
@require_POST
def coach_memory_delete(request, fact_id):
    fact = get_object_or_404(CareerMemoryFact, id=fact_id, user=request.user)
    fact.delete()
    messages.success(request, 'The memory item has been deleted.')
    return redirect(_safe_return_url(request))


@login_required
def coach_memory_edit(request, fact_id):
    fact = get_object_or_404(CareerMemoryFact, id=fact_id, user=request.user)
    form = CareerMemoryEditForm(request.POST or None, instance=fact)
    if request.method == 'POST' and form.is_valid():
        edited = form.save(commit=False)
        edited.user_confirmed = True
        edited.review_status = 'confirmed'
        edited.source_label = f'User edited · {edited.source_label or edited.get_source_type_display()}'[:255]
        edited.source_type = 'manual'
        edited.fingerprint = memory_fingerprint(edited.category, edited.title, edited.content)
        edited.save()
        messages.success(request, 'Career Memory item updated and confirmed.')
        return redirect('coach_dashboard')
    return render(request, 'prep_app/coach_memory_edit.html', {'form': form, 'fact': fact})


@login_required
@require_POST
def coach_memory_reject(request, fact_id):
    fact = get_object_or_404(CareerMemoryFact, id=fact_id, user=request.user)
    fact.user_confirmed = False
    fact.review_status = 'rejected'
    fact.save(update_fields=['user_confirmed', 'review_status', 'updated_at'])
    messages.success(request, 'The suggestion was rejected and will not be used.')
    return redirect(_safe_return_url(request))


@login_required
@require_POST
def coach_start(request):
    profile, _ = CareerProfile.objects.get_or_create(user=request.user)
    form = StartInterviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Add a target role before starting the interview.')
        return redirect('coach_dashboard')

    target_role = form.cleaned_data['target_role']
    job_description = form.cleaned_data['job_description']
    focus_areas = form.cleaned_data['focus_areas']
    category = form.cleaned_data['category']
    language = form.cleaned_data['language'] or profile.preferred_language
    question = InterviewCoachService().generate_initial_question(
        request.user,
        profile,
        target_role,
        job_description,
        focus_areas,
        language,
    )
    plan = build_interview_plan(category)
    session = InterviewSession.objects.create(
        user=request.user,
        target_role=target_role,
        job_description=job_description,
        focus_areas=focus_areas,
        category=category,
        language=language,
        plan_sections=plan,
        current_section=plan[0]['key'],
        current_section_index=0,
        current_question=question,
    )
    if not profile.target_role:
        profile.target_role = target_role
        profile.save(update_fields=['target_role', 'updated_at'])
    return redirect('coach_session', session_id=session.id)


@login_required
def coach_session(request, session_id):
    session = get_object_or_404(
        InterviewSession.objects.prefetch_related('turns'),
        id=session_id,
        user=request.user,
    )
    context = {
        'session': session,
        'answer_form': InterviewAnswerForm(),
        'turns': session.turns.all(),
        'skills': request.user.skill_evidence.all()[:12],
        'memory': request.user.career_memory.filter(
            user_confirmed=True, review_status='confirmed'
        )[:8],
    }
    return render(request, 'prep_app/coach_session.html', context)


@login_required
@require_POST
def coach_answer(request, session_id):
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    if session.status != 'active':
        messages.info(request, 'This interview has already been completed.')
        return redirect('coach_session', session_id=session.id)

    form = InterviewAnswerForm(request.POST)
    if form.is_valid():
        turn = InterviewCoachService().record_answer(session, form.cleaned_data['answer'])
        if turn is None:
            # The session was completed by a concurrent request while this
            # answer was being assessed.
            messages.info(request, 'This interview has already been completed.')
        else:
            messages.success(request, 'Answer assessed. The next question has adapted to your evidence.')
    else:
        messages.error(request, 'Please give a little more detail before submitting your answer.')
    return redirect('coach_session', session_id=session.id)


@login_required
@require_POST
def coach_finish(request, session_id):
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    if session.status == 'active':
        InterviewCoachService().complete_session(session)
        messages.success(request, 'Interview completed. Your honest assessment is ready.')
    return redirect('coach_session', session_id=session.id)


@login_required
@require_POST
def coach_session_delete(request, session_id):
    session = get_object_or_404(InterviewSession, id=session_id, user=request.user)
    form = SessionDeleteForm(request.POST)
    if form.is_valid() and form.cleaned_data['delete_generated_memory']:
        session.memory_updates.filter(user=request.user).delete()
    session.delete()
    messages.success(request, 'Interview session deleted.')
    return redirect('coach_dashboard')


def _safe_return_url(request):
    candidate = request.POST.get('next', '')
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return 'coach_dashboard'
