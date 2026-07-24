import logging
import re
try:
    from google import genai
except ImportError:
    from .mock_genai import genai

import json

from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, update_session_auth_hash
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.contrib.auth.views import (LoginView, PasswordResetView, PasswordResetDoneView, PasswordResetCompleteView, PasswordResetConfirmView)
from django.urls import reverse_lazy, reverse
from django.conf import settings
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from .forms import JobInfoForm, CustomAuthenticationForm, CustomUserCreationForm, CodeSubmissionForm
from .models import Topic, Question, UserSubmission, UserCode
from .services.ai_client import request_timeout_ms
from .services.rate_limit import rate_limit
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import PasswordChangeForm

logger = logging.getLogger(__name__)


def home(request):
    return render(request, 'prep_app/home.html')

class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'prep_app/login_logout_folder/login.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        remember_me = form.cleaned_data.get('remember_me')
        username = form.cleaned_data.get('username')
        
        # Call parent's form_valid to authenticate user
        response = super().form_valid(form)
        
        if remember_me:
            # Set session expiry to 30 days
            self.request.session.set_expiry(30 * 24 * 60 * 60)
            
            if username:
                # Set cookie for username
                response.set_cookie(
                    'remembered_username',
                    username,
                    max_age=30 * 24 * 60 * 60,  # 30 days
                    httponly=True,  # Cookie not accessible via JavaScript
                    samesite='Strict'  # CSRF protection
                )
        else:
            # Delete the cookie if "remember me" is not checked
            response.delete_cookie('remembered_username')
            self.request.session.set_expiry(0)
            
        return response

    def form_invalid(self, form):
        messages.error(
            self.request,
            'Invalid username or password. Please try again.',
            extra_tags='error'
        )
        return super().form_invalid(form)

    def get_initial(self):
        initial = super().get_initial()
        # Pre-fill username if cookie exists
        remembered_username = self.request.COOKIES.get('remembered_username')
        if remembered_username:
            initial['username'] = remembered_username
        return initial

@method_decorator(
    rate_limit(
        'password_reset', limit=5, window_seconds=3600,
        message='Too many password reset requests. Please wait a while before trying again.',
    ),
    name='post',
)
class CustomPasswordResetView(PasswordResetView):
    template_name = 'prep_app/login_logout_folder/password_reset_form.html'
    email_template_name = 'prep_app/login_logout_folder/password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'prep_app/login_logout_folder/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'prep_app/login_logout_folder/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'prep_app/login_logout_folder/password_reset_complete.html'


@rate_limit(
    'register', limit=10, window_seconds=3600,
    message='Too many sign-up attempts from this connection. Please wait a while and try again.',
)
def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            # Log the user in after registration
            login(request, user)
            messages.success(request, f'Account created successfully for {username}')
            return redirect('login')
        else:
            # If form is not valid, errors will be shown in the template
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'prep_app/login_logout_folder/register.html', {'form': form})


@login_required
def your_profile(request):
    # Initialize the password change form
    password_form = PasswordChangeForm(user=request.user, data=request.POST or None)
    
    if request.method == 'POST':
        # If the form is valid, save the new password and keep the user logged in
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('your_profile')  # Redirect to the profile page to reload the form
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return render(request, 'prep_app/your_profile.html', {
        'password_form': password_form,
    })

def analyze_job_description(job_role, company_name, job_description):
    """Summarise a job description, or fall back to a deterministic outline.

    Mirrors the boundary the coach services use: ask for JSON, normalize every
    field, and never let a model failure reach the user as an exception.
    """
    result = _request_job_analysis(job_role, company_name, job_description)
    if result is None:
        return _fallback_job_analysis(job_role, company_name, job_description)
    return result


def _request_job_analysis(job_role, company_name, job_description):
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return None

    prompt = f"""
    Analyze the following job description for {job_role} at {company_name}:

    {job_description[:6000]}

    Provide the following information:
    1. Simplified job description (2-3 sentences)
    2. Skills required (return as a list)
    3. Key benefits (return as a list)
    4. Future interview process steps (list of 3-5 likely steps)

    Return JSON only, with keys 'simplified_description', 'skills', 'benefits'
    and 'interview_steps'.
    """

    try:
        client = genai.Client(api_key=api_key, http_options={'timeout': request_timeout_ms()})
        response = client.models.generate_content(
            model=getattr(settings, 'INTERVIEW_COACH_MODEL', 'gemini-2.5-flash-lite'),
            contents=prompt,
            config={"temperature": 0, "response_mime_type": "application/json"},
        )
        parsed = json.loads(response.text.strip().replace('```json', '').replace('```', '').strip())
    except Exception:
        # Any model, network or parse failure degrades to the outline below.
        return None
    if not isinstance(parsed, dict):
        return None

    def _list(value):
        if not isinstance(value, list):
            return []
        return [str(item).strip()[:200] for item in value if str(item).strip()][:12]

    return {
        'simplified_description': str(parsed.get('simplified_description', '')).strip()[:2000],
        'skills': _list(parsed.get('skills')),
        'benefits': _list(parsed.get('benefits')),
        'interview_steps': _list(parsed.get('interview_steps')),
    }


def _fallback_job_analysis(job_role, company_name, job_description):
    """Honest, deterministic outline used when the model is unavailable."""
    quick = _quick_cv_vs_jd(job_description, '')
    return {
        'simplified_description': (
            f'Automatic summarising is unavailable right now, so this is taken directly from the '
            f'posting for {job_role} at {company_name}. Read the full description below for detail.'
        ),
        'skills': quick['job_skills'][:12],
        'benefits': [],
        'interview_steps': [
            'Application review',
            'Introductory call with a recruiter',
            'Technical or role-specific interview',
            'Final interview with the hiring manager',
        ],
    }
def _quick_cv_vs_jd(job_description: str, cv_content: str) -> dict:
    # Deterministic, fast heuristic analysis for immediate UI feedback
    import re
    from collections import Counter
    canonical_skills = {
        'python','java','javascript','typescript','node','react','django','flask','spring','kotlin',
        'go','golang','c++','c#','ruby','rails','php','laravel','swift','objective-c',
        'aws','gcp','azure','docker','kubernetes','terraform','ansible',
        'sql','mysql','postgresql','postgres','sqlite','mongodb','redis','kafka','spark','hadoop',
        'pandas','numpy','scikit-learn','sklearn','pytorch','tensorflow','airflow',
        'git','linux','bash','jira','confluence','agile','scrum','ci/cd','ci', 'cd',
        # Domain terms for the provided JD
        'digital health','healthcare','healthcare settings','patient flow','emergency department',
        'clinicians','healthcare systems','business analysis','systems analysis','project management',
        'software developers','app design','app deployment','international travel','bupa','life insurance'
    }
    stopwords = {
        'the','and','for','with','from','that','this','your','you','our','their','are','will','have','has','to','of','in','on','at','as','by','or','an','a','be','is','it','we','they','them','work','team','project','projects','experience','years','strong','ability','skills','using','use'
    }

    def norm_tokens(text: str) -> list[str]:
        t = re.sub(r"[^a-zA-Z0-9+#+/.-]+", " ", text.lower())
        parts = [p for p in t.split() if p and p not in stopwords and len(p) >= 3]
        # normalize aliases
        aliases = []
        if 'postgres' in parts: aliases.append('postgresql')
        if 'js' in parts: aliases.append('javascript')
        if 'ts' in parts: aliases.append('typescript')
        if 'ci' in parts or 'cd' in parts: aliases.append('ci/cd')
        return parts + aliases

    jd_tokens = norm_tokens(job_description)
    cv_tokens = norm_tokens(cv_content)

    # Keyword frequencies from JD (top 12)
    jd_counts = Counter(jd_tokens)
    top_keywords = [(w, c) for w, c in jd_counts.most_common(12) if w not in canonical_skills]

    job_skills = sorted([s for s in canonical_skills if s in set(jd_tokens)])
    cv_skills = sorted([s for s in canonical_skills if s in set(cv_tokens)])

    matched = sorted([s for s in job_skills if s in set(cv_skills)])
    missing = sorted([s for s in job_skills if s not in set(cv_skills)])

    # Balanced coverage: avoid 100% when JD mentions very few skills
    effective_denominator = max(8, len(job_skills))  # require ~8 JD skills for full-scale scores
    coverage = int(round(100 * (len(matched) / effective_denominator))) if effective_denominator else 0
    return {
        'keywords': top_keywords,
        'job_skills': job_skills,
        'cv_skills': cv_skills,
        'missing_skills': missing,
        'match_score': coverage
    }


@login_required(login_url='/login/')
def ai_job_info(request):
    if request.method == 'POST':
        form = JobInfoForm(request.POST)
        if form.is_valid():
            job_role = form.cleaned_data['job_role']
            company_name = form.cleaned_data['company_name']
            job_description = form.cleaned_data['job_description']
        
            analysis = analyze_job_description(job_role, company_name, job_description)

            return render(request, 'prep_app/job_info_results.html', {'analysis': analysis, 'job_role': job_role, 'company_name': company_name})
        
    else:
        form = JobInfoForm()
    return render(request, 'prep_app/job_info.html', {'form': form})


## AI resume builder upload removed


## AI resume builder JD removed


## AI resume builder questions removed


## AI resume builder preview removed


## AI resume full preview removed


## AI resume DOCX helper removed


## AI resume builder download removed


## AI resume builder save edits removed


def customer_support(request):
    return render(request, 'prep_app/customer_support.html')


def topic_list(request):
    topics = Topic.objects.all()
    return render(request, 'prep_app/topic_list.html', {
        'topics': topics
    })

def question_list(request, topic_slug):
    topic = get_object_or_404(Topic, slug=topic_slug)
    
    questions = topic.questions.all()
    return render(request, 'prep_app/question_list.html', {
        'topic': topic,
        'questions': questions
    })

@login_required
def coding_assessment(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    
    if request.method == 'POST':
        form = CodeSubmissionForm(request.POST)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.user = request.user
            submission.question = question
            submission.save()
            
            # Here you would typically run the code against test cases
            # For now, we'll just return a success response
            return JsonResponse({
                'status': 'success',
                'message': 'Code submitted successfully'
            })
    else:
        form = CodeSubmissionForm(initial={'code': question.initial_code})

    return render(request, 'prep_app/coding_assessment.html', {
        'question': question,
        'form': form,
        'initial_code': question.initial_code,
        'submissions': UserSubmission.objects.filter(
            user=request.user,
            question=question
        ).order_by('-created_at')[:5]
    })

@login_required
@csrf_protect
def run_code(request, question_id):
    """Retained as a safe compatibility target; execution requires a real sandbox."""
    return JsonResponse({
        'status': 'disabled',
        'message': 'Code execution is disabled until an isolated sandbox is available.',
    }, status=410)

    
@login_required
@require_http_methods(["POST"])
def save_code(request, question_id):
    question = get_object_or_404(Question, id=question_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Malformed request body'}, status=400)

    code = data.get('code')
    language = data.get('language')
    if not isinstance(code, str) or not isinstance(language, str) or not language.strip():
        return JsonResponse(
            {'status': 'error', 'message': 'Both code and language are required'}, status=400,
        )

    user_code, _ = UserCode.objects.update_or_create(
        user=request.user,
        question=question,
        language=language[:20],
        defaults={'code': code},
    )
    return JsonResponse({
        'status': 'success',
        'message': 'Code saved successfully',
        'last_modified': user_code.last_modified.isoformat(),
    })

@login_required
def get_saved_code(request, question_id):
    language = request.GET.get('language', 'python')
    user_code = UserCode.objects.filter(
        user=request.user,
        question_id=question_id,
        language=language,
    ).first()

    if user_code is None:
        return JsonResponse({'status': 'not_found', 'code': None})
    return JsonResponse({
        'status': 'success',
        'code': user_code.code,
        'language': user_code.language,
        'last_modified': user_code.last_modified.isoformat(),
    })
    

def serialize_object(obj):
    """Convert complex objects to JSON-serializable format"""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [serialize_object(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize_object(v) for k, v in obj.items()}
    elif hasattr(obj, 'to_dict'):
        try:
            result = obj.to_dict()
            # Recursively serialize the result to handle nested objects
            return serialize_object(result)
        except Exception as e:
            print(f"Warning: to_dict() failed for {type(obj).__name__}: {e}")
            # Fall back to __dict__ approach
            pass
    
    # Handle objects with __dict__
    if hasattr(obj, '__dict__'):
        result = {}
        for key, value in obj.__dict__.items():
            # Skip private attributes and methods
            if key.startswith('_'):
                continue
            try:
                serialized_value = serialize_object(value)
                result[key] = serialized_value
            except Exception as e:
                print(f"Warning: Could not serialize {key} in {type(obj).__name__}: {e}")
                # Convert to string as fallback
                try:
                    result[key] = str(value)
                except:
                    # Skip completely if even string conversion fails
                    continue
        return result
    
    # Last resort: convert to string
    try:
        return str(obj)
    except Exception:
        return f"<{type(obj).__name__} object>"

## AI resume loading endpoints removed

@login_required
@require_http_methods(["POST"])
def file_upload(request):
    """Minimal upload endpoint used by CV Analysis front-end.
    Accepts file(s) and returns success; does not persist content.
    """
    uploaded = list(request.FILES.keys())
    if not uploaded:
        return JsonResponse({'status': 'error', 'message': 'No files provided'}, status=400)
    try:
        # Drain file streams without persisting
        for _key, handle in request.FILES.items():
            handle.read()
    except Exception:
        logger.exception('Failed to read an uploaded file')
        return JsonResponse({'status': 'error', 'message': 'Could not read the upload'}, status=400)
    return JsonResponse({'status': 'success', 'files': uploaded})
