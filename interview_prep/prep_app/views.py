import re
import ast 
try:
    from google import genai
except ImportError:
    from .mock_genai import genai
import io
import PyPDF2
import subprocess
import tempfile

# Import AI Resume Builder views
from .ai_resume_views import (
    ai_resume_upload, ai_resume_editor, ai_resume_download,
    ai_resume_export_pdf, ai_resume_export_docx, ai_resume_refine,
    ai_resume_save, ai_resume_clear_session
)
import json 
import os
import requests
import logging
import random
import time
from typing import List

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
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
import json
from .forms import JobInfoForm, UserProfileForm, CVAnalysisForm, CustomAuthenticationForm, CustomUserCreationForm, CodeSubmissionForm
from .models import Topic, Question, UserSubmission, UserCode
from django.contrib.auth.forms import PasswordChangeForm

from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# API key is now passed directly to the client

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
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = f"""
    Analyze the following job description for {job_role} at {company_name}:

    {job_description}

    Provide the following information:
    1. Simplified job description (2-3 sentences)
    2. Skills required (return as a list)
    3. Key benefits (return as a list)
    4. Future interview process steps (list of 3-5 likely steps)

    Format the output as a Python dictionary with keys: 'simplified_description', 'skills', 'benefits', and 'interview_steps'.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config={"temperature": 0}
    )
    clean_response = response.text.replace("```python", "").replace("```", "").strip()

    print (clean_response)
    analysis = ast.literal_eval(clean_response.strip())

    # analysis['skills'] = [skill.strip() for skill in analysis['skills'].split(",")]
    # analysis['benefits'] = [benefit.strip() for benefit in analysis['benefits'].split(".") if benefit]

    return analysis
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


def _filter_question_skills(missing_skills: List[str]) -> List[str]:
    # Deterministically keep role-relevant skills and exclude obvious benefits/perks
    canonical_skills = {
        'python','java','javascript','typescript','node','react','react.js','node.js','django','flask','spring','kotlin',
        'go','golang','c++','c#','ruby','rails','php','laravel','swift','objective-c',
        'aws','gcp','azure','docker','kubernetes','terraform','ansible',
        'sql','mysql','postgresql','postgres','sqlite','mongodb','redis','kafka','spark','hadoop',
        'pandas','numpy','scikit-learn','sklearn','pytorch','tensorflow','airflow',
        'git','linux','bash','jira','confluence','agile','scrum','ci/cd','api development','system integration',
        'html','css','tailwind css','typescript','react native','postgresql'
    }
    domain_soft = {
        'business analysis','systems analysis','project management','data analysis','data visualization','reporting',
        'stakeholder management','process optimization','decision making','analytical thinking','technical solutions',
        'software development','full-stack','nlp','classification models','ui rendering','memory optimization'
    }
    domain_health = {
        'healthcare','digital health','patient flow','hospital management'
    }
    banned_contains = ['bupa', 'insurance', 'allowance', 'pub', 'visa', 'licence', 'license', 'travel']

    allowed = set(s.lower() for s in (canonical_skills | domain_soft | domain_health))
    filtered: list[str] = []
    seen = set()
    for s in missing_skills:
        key = (s or '').strip().lower()
        if not key or key in seen:
            continue
        if any(bt in key for bt in banned_contains):
            continue
        if key in allowed:
            filtered.append(s)
            seen.add(key)
            continue
        # Heuristic: keep short 1-2 word technical phrases
        if len(key.split()) <= 2 and any(ch.isalpha() for ch in key):
            filtered.append(s)
            seen.add(key)
    return filtered


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



def user_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES)
        if form.is_valid():
            # Process the form data
            # You can save it to the database or pass it to the next step
            # For now, we'll just redirect to the job description page
            return redirect('job_description')
    else:
        form = UserProfileForm()
    
    return render(request, 'user_profile.html', {'form': form})


def parse_ai_response(response_text):
    # Remove any markdown code block syntax
    clean_response = response_text.replace("```python", "").replace("```", "").strip()
    
    
    # Try to parse as JSON first (simpler and more reliable)
    try:
        import json
        result = json.loads(clean_response)
        return result
    except json.JSONDecodeError:
        pass
    
    # Initialize the result dictionary
    result = {
        'keywords': [],
        'job_skills': [],
        'cv_skills': [],
        'missing_skills': [],
        'match_score': 0
    }
    
    # Parse keywords
    keywords_match = re.search(r"'keywords':\s*\[(.*?)\]", clean_response, re.DOTALL)
    if keywords_match:
        keywords_str = keywords_match.group(1)
        keywords = re.findall(r"\('([^']+)',\s*(\d+)\)", keywords_str)
        result['keywords'] = [{'word': word, 'count': int(count)} for word, count in keywords]
    
    # Parse job_skills
    job_skills_match = re.search(r"'job_skills':\s*\[(.*?)\]", clean_response, re.DOTALL)
    if job_skills_match:
        result['job_skills'] = [skill.strip(" '") for skill in job_skills_match.group(1).split(',')]
    
    # Parse cv_skills
    cv_skills_match = re.search(r"'cv_skills':\s*\[(.*?)\]", clean_response, re.DOTALL)
    if cv_skills_match:
        result['cv_skills'] = [skill.strip(" '").replace("'", "") for skill in cv_skills_match.group(1).split(',')]
        
    # Parse missing_skills
    missing_skills_match = re.search(r"'missing_skills':\s*\[(.*?)\]", clean_response, re.DOTALL)
    if missing_skills_match:
        result['missing_skills'] = [skill.strip(" '").replace("'", "") for skill in missing_skills_match.group(1).split(',')]
    
    # Parse match_score
    match_score_match = re.search(r"'match_score':\s*(\d+)", clean_response)
    if match_score_match:
        result['match_score'] = int(match_score_match.group(1))
    
    for i in result['cv_skills']:
        i = i.replace("'", "")
    return result

def analyze_cv(job_role: str, company_name: str, job_description: str, cv_content: str) -> dict:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = f"""
        Compare this CV against this job description and return ONLY a JSON object with these exact keys:

        Job Description:
        {job_description}

        CV/Resume:
        {cv_content}

        Extract skills and calculate match. Return ONLY this JSON format:
        {{
            "keywords": [("word", count), ("phrase", count)],
            "job_skills": ["Python", "React", "etc"],
            "cv_skills": ["Python", "Java", "etc"], 
            "missing_skills": ["Git", "AWS", "etc"],
            "match_score": 75
        }}

        Rules:
        - job_skills: Technical skills mentioned in the job description
        - cv_skills: Technical skills found in the CV/resume  
        - missing_skills: Skills in job_skills but NOT in cv_skills
        - match_score: Percentage of job_skills that are also in cv_skills
        - keywords: Important words from job description with their frequency
        
        Focus on: programming languages, frameworks, tools, databases, methodologies.
        Normalize similar terms (js→javascript, react.js→react, etc).
        
        Return ONLY the JSON object, no other text.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config={"temperature": 0}
    )


    analysis = parse_ai_response(response.text)
    return analysis

@login_required(login_url='/login/')
def cv_analysis(request):
    if request.method == 'POST':
        form = CVAnalysisForm(request.POST, request.FILES)
        if form.is_valid():
            job_role = form.cleaned_data['job_role']
            company_name = form.cleaned_data['company_name']
            job_description = form.cleaned_data['job_description']
            cv_file = form.cleaned_data['cv_file']

            
            cv_content = ""
            if cv_file:
                if cv_file.name.endswith('.pdf'):
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(cv_file.read()))
                    for page in pdf_reader.pages:
                        cv_content += page.extract_text()
                else:  
                    cv_content = cv_file.read().decode('utf-8')

                analysis = analyze_cv(job_role, company_name, job_description, cv_content)
                # Fallback to deterministic heuristic if AI parsing returns empty/minimal data
                try:
                    if not isinstance(analysis, dict):
                        analysis = {}
                    job_skills = analysis.get('job_skills') or []
                    cv_skills = analysis.get('cv_skills') or []
                    if len(job_skills) == 0 and len(cv_skills) == 0:
                        quick = _quick_cv_vs_jd(job_description, cv_content)
                        # Merge preserving any non-empty keys from AI
                        merged = {**quick, **{k: v for k, v in analysis.items() if v}}
                        analysis = merged
                except Exception:
                    analysis = _quick_cv_vs_jd(job_description, cv_content)

                analysis_json = json.dumps(analysis)

                return render(request, 'prep_app/cv_analysis_results.html', {
                    'analysis_json': analysis_json,
                    'job_role': job_role,
                    'company_name': company_name
                })
            else:
                return render(request, 'prep_app/cv_analysis.html', {'form': form, 'error': 'Error: Cannot find your resume!'})
        
    else:
        form = CVAnalysisForm()
    return render(request, 'prep_app/cv_analysis.html', {'form': form})

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
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        code = data.get('code')
        language = data.get('language', 'python')
        
        # Get the question and test cases
        question = get_object_or_404(Question, id=question_id)
        test_cases = question.test_cases
        title = question.title
        
        # Generate a filename based on the question title and language
        function_name = title.replace(" ", "_").lower()
        sanitized_title = ''.join(c for c in function_name if c.isalnum() or c == '_')
        
        # Define file extensions and run commands for each language
        language_configs = {
            'python': {
                'extension': '.py',
                'command': ['python'],
                'function_template': 'result = {}({})',
            },
            'java': {
                'extension': '.java',
                'command': ['java'],
                'function_template': 'result = solution.{}({})',
            },
            'javascript': {
                'extension': '.js',
                'command': ['node'],
                'function_template': 'result = {}({})',
            },
            'cpp': {
                'extension': '.cpp',
                'command': ['g++', '-o'],
                'function_template': 'result = {}({})',
            }
        }
        
        if language not in language_configs:
            return JsonResponse({'status': 'error', 'message': 'Unsupported language'}, status=400)
        
        temp_dir = '/Users/hillmanchan/Desktop/interview_prep_proj/interview_prep/static/temp_files'
        config = language_configs[language]
        file_name = os.path.join(temp_dir, f"{sanitized_title}{config['extension']}")
        
        # Extract function name from the initial code template based on language
        initial_code_dict = json.loads(question.initial_code) if isinstance(question.initial_code, str) else question.initial_code
        function_pattern = {
            'python': r'def\s+(\w+)\s*\(',
            'java': r'public\s+\w+\s+(\w+)\s*\(',
            'javascript': r'function\s+(\w+)\s*\(',
            'cpp': r'\w+\s+(\w+)\s*\('
        }
        
        match = re.search(function_pattern[language], initial_code_dict[language])
        if match:
            actual_function_name = match.group(1)
        else:
            return JsonResponse({'status': 'error', 'message': 'Could not extract function name'}, status=400)
        
        # Write code to language-specific file
        with open(file_name, 'w') as f:
            if language == 'java':
                f.write('public class Solution {\n')
                f.write(code)
                f.write('\n    public static void main(String[] args) {\n')
                f.write('        Solution solution = new Solution();\n')

            elif language == 'javascript':
                f.write(code)
                f.write('\n\nconst results = [];\n')

            elif language == 'cpp':
                f.write('#include <iostream>\n#include <vector>\n#include <string>\n#include <json/json.h>\n')
                f.write(code)
                f.write('\n\nint main() {\n')
                
            else:  # python
                f.write(code)
                f.write('\n\n# Test runner\n')
                f.write('import json\n')
                f.write('results = []\n')
            
            # Add test cases according to language
            for i, test_case in enumerate(test_cases):
                test_input = test_case.get('input', {})
                expected_output = test_case.get("expected", "No expected output")
                
                if isinstance(test_input, dict) and len(test_input) > 1:
                    params_str = ', '.join([f"{k}={repr(v)}" for k, v in test_input.items()])
                else:
                    params_str = json.dumps(test_input)
                
                if language == 'python':
                    f.write(f'\ntry:\n')
                    f.write(f'    result = {actual_function_name}({params_str})\n')
                    f.write(f'    results.append({{"index": {i}, "actual_output": result, "expected": {json.dumps(expected_output)}, "passed": result == {json.dumps(expected_output)}}})\n')
                    f.write('except Exception as e:\n')
                    f.write(f'    results.append({{"index": {i}, "actual_output": str(e), "expected": {json.dumps(expected_output)}, "passed": False}})\n')
                
                # Add language-specific test runners here for other languages...
                # Modify the language handling part in run_code function:
                elif language == 'java':
                    write_java_test_file(file_name, code, test_cases, actual_function_name)
            # Close the main function/class for compiled languages
            if language == 'java':
                f.write('    }\n}')
            elif language == 'cpp':
                f.write('    return 0;\n}')
            
            if language == 'python':
                pass
        
        # Execute the code based on language
        try:
            if language == 'python':
                process = subprocess.run(
                    ['python', file_name],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if process.returncode == 0:
                    test_results = json.loads(process.stdout)
                    all_passed = all(result['passed'] for result in test_results)
                    return JsonResponse({
                        'status': 'success',
                        'test_results': test_results,
                        'all_passed': all_passed
                    })
                else:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Execution error: {process.stderr}'
                    })
            else:
                # Add execution logic for other languages here
                return JsonResponse({
                    'status': 'error',
                    'message': f'Language {language} execution not implemented yet'
                })
                
        except subprocess.TimeoutExpired:
            return JsonResponse({
                'status': 'error',
                'message': 'Code execution timed out'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error processing request: {str(e)}'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error processing request: {str(e)}'
        }, status=400)

    
@login_required
@require_http_methods(["POST"])
def save_code(request, question_id):
    try:
        data = json.loads(request.body)
        code = data.get('code')
        language = data.get('language')
        
        # Update or create the UserCode instance
        user_code, created = UserCode.objects.update_or_create(
            user=request.user,
            question_id=question_id,
            language=language,
            defaults={'code': code}
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Code saved successfully',
            'last_modified': user_code.last_modified.isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def get_saved_code(request, question_id):
    try:
        language = request.GET.get('language', 'python')  # Default to python
        user_code = UserCode.objects.filter(
            user=request.user,
            question_id=question_id,
            language=language
        ).first()
        
        if user_code:
            print (user_code.code, user_code.language)
            return JsonResponse({
                'status': 'success',
                'code': user_code.code,
                'language': user_code.language,
                'last_modified': user_code.last_modified.isoformat()
            })
        else:
            return JsonResponse({
                'status': 'not_found',
                'code': None
            })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
    

def write_java_test_file(file_name, code, test_cases, actual_function_name):
    """Write a properly formatted Java test file."""
    with open(file_name, 'w') as f:
        # Add imports
        f.write('import java.util.*;\n')
        f.write('import org.json.*;\n\n')
        
        # Start Solution class
        f.write('public class Solution {\n')
        
        # Write the submitted solution code (without the class declaration)
        if 'public class Solution' in code:
            # Extract just the method from the submitted code
            method_start = code.find('{') + 1
            method_end = code.rfind('}')
            f.write(code[method_start:method_end])
        else:
            f.write(code)
        
        # Add main method for testing
        f.write('\n    public static void main(String[] args) {\n')
        f.write('        Solution solution = new Solution();\n')
        f.write('        List<Map<String, Object>> results = new ArrayList<>();\n\n')
        
        # Add test cases
        for i, test_case in enumerate(test_cases):
            test_input = test_case.get('input', [])
            expected_output = test_case.get('expected')
            
            f.write(f'        // Test case {i + 1}\n')
            f.write('        try {\n')
            
            # Handle input array
            array_str = ', '.join(str(x) for x in test_input)
            f.write(f'            int[] nums = new int[]{{{array_str}}};\n')
            
            # Call method and store result
            f.write(f'            int result = solution.{actual_function_name}(nums);\n')
            
            # Create result map
            f.write('            Map<String, Object> testResult = new HashMap<>();\n')
            f.write(f'            testResult.put("index", {i});\n')
            f.write('            testResult.put("actual_output", result);\n')
            f.write(f'            testResult.put("expected", {expected_output});\n')
            f.write(f'            testResult.put("passed", result == {expected_output});\n')
            f.write('            results.add(testResult);\n')
            
            # Add catch block
            f.write('        } catch (Exception e) {\n')
            f.write('            Map<String, Object> testResult = new HashMap<>();\n')
            f.write(f'            testResult.put("index", {i});\n')
            f.write('            testResult.put("actual_output", e.toString());\n')
            f.write(f'            testResult.put("expected", {expected_output});\n')
            f.write('            testResult.put("passed", false);\n')
            f.write('            results.add(testResult);\n')
            f.write('        }\n\n')
        
        # Add JSON output
        f.write('        // Convert results to JSON and print\n')
        f.write('        System.out.println(new JSONArray(results).toString());\n')
        
        # Close main method and class
        f.write('    }\n')
        f.write('}\n')



class JobScraper:
    def __init__(self, timeout=15):
        # Advanced logging
        logging.basicConfig(level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)

        # Chrome WebDriver with extensive options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        
        # User agent rotation
        self.ua = UserAgent()
        chrome_options.add_argument(f"user-agent={self.ua.random}")

        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            self.driver.set_page_load_timeout(timeout)
        except Exception as e:
            self.logger.error(f"WebDriver initialization error: {e}")
            raise

    def _safe_get(self, url):
        """Safely load URL with error handling"""
        try:
            self.driver.get(url)
            time.sleep(random.uniform(2, 5))  # Random delay
            return True
        except TimeoutException:
            self.logger.error(f"Timeout loading {url}")
        except WebDriverException as e:
            self.logger.error(f"WebDriver error loading {url}: {e}")
        return False

    def scrape_linkedin(self, role, location):
        jobs = []
        try:
            url = f"https://www.linkedin.com/jobs/search?keywords={role}&location={location}"
            if not self._safe_get(url):
                return jobs

            try:
                # Wait for job listings to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.base-card'))
                )
            except TimeoutException:
                self.logger.warning("No job listings found on LinkedIn")
                return jobs

            # Find job listings
            job_listings = self.driver.find_elements(By.CSS_SELECTOR, 'div.base-card')
            self.logger.info(f"Found {len(job_listings)} LinkedIn jobs")

            for job in job_listings[:5]:
                try:
                    title = job.find_element(By.CSS_SELECTOR, 'h3.base-search-card__title').text
                    company = job.find_element(By.CSS_SELECTOR, 'h4.base-search-card__subtitle').text
                    apply_url = job.find_element(By.CSS_SELECTOR, 'a.base-card__full-link').get_attribute('href')
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'post_date': datetime.now().strftime('%Y-%m-%d'),
                        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
                        'apply_url': apply_url,
                        'source': 'LinkedIn'
                    })
                except Exception as e:
                    self.logger.error(f"Error extracting LinkedIn job: {e}")
        
        except Exception as e:
            self.logger.error(f"Error scraping LinkedIn: {str(e)}")
        
        return jobs

    def scrape_indeed(self, role, location):
        jobs = []
        url_SE_Leeds_West_Yorkshure_hybrid_5miles ='https://uk.indeed.com/jobs?q=software+engineer&l=Leeds%2C+West+Yorkshire&sc=0kf%3Aattr%28PAXZC%29%3B&radius=5&fromage=last&vjk=068a06f87745ffc6'
        url_SE_Leeds_West_Yorkshure_Last3days_5miles = 'https://uk.indeed.com/jobs?q=software+engineer&l=Leeds%2C+West+Yorkshire&radius=5&fromage=3&vjk=068a06f87745ffc6'
        url_SEA = 'https://uk.indeed.com/jobs?q=software%20engineer%20apprenticeship&l=&from=searchOnDesktopSerp'
        url_JSD = 'https://uk.indeed.com/jobs?q=junior+software+developer&l=&from=searchOnDesktopSerp&vjk=5c438be06df61aa0'
        try:
            url = f"https://www.indeed.com/jobs?q={role}&l={location}"
            if not self._safe_get(url):
                return jobs

            try:
                # Wait for job listings to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.job_seen_beacon'))
                )
            except TimeoutException:
                self.logger.warning("No job listings found on Indeed")
                return jobs

            job_listings = self.driver.find_elements(By.CSS_SELECTOR, 'div.job_seen_beacon')
            self.logger.info(f"Found {len(job_listings)} Indeed jobs")

            for job in job_listings[:5]:
                try:
                    title = job.find_element(By.CSS_SELECTOR, 'h2.jobTitle').text
                    company = job.find_element(By.CSS_SELECTOR, 'span.companyName').text
                    apply_url = job.find_element(By.CSS_SELECTOR, 'a.jcs-JobTitle').get_attribute('href')
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'post_date': datetime.now().strftime('%Y-%m-%d'),
                        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
                        'apply_url': apply_url,
                        'source': 'Indeed'
                    })
                except Exception as e:
                    self.logger.error(f"Error extracting Indeed job: {e}")
        
        except Exception as e:
            self.logger.error(f"Error scraping Indeed: {str(e)}")
        
        return jobs

    def scrape_glassdoor(self, role, location):
        jobs = []
        try:
            url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={role}&locT=C&locId={location}"
            if not self._safe_get(url):
                return jobs

            try:
                # Wait for job listings to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'li.react-job-listing'))
                )
            except TimeoutException:
                self.logger.warning("No job listings found on Glassdoor")
                return jobs

            job_listings = self.driver.find_elements(By.CSS_SELECTOR, 'li.react-job-listing')
            self.logger.info(f"Found {len(job_listings)} Glassdoor jobs")

            for job in job_listings[:5]:
                try:
                    title = job.find_element(By.CSS_SELECTOR, 'a.jobLink').text
                    company = job.find_element(By.CSS_SELECTOR, 'div.jobHeader').text
                    apply_url = job.find_element(By.CSS_SELECTOR, 'a.jobLink').get_attribute('href')
                    
                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'post_date': datetime.now().strftime('%Y-%m-%d'),
                        'end_date': (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'),
                        'apply_url': apply_url,
                        'source': 'Glassdoor'
                    })
                except Exception as e:
                    self.logger.error(f"Error extracting Glassdoor job: {e}")
        
        except Exception as e:
            self.logger.error(f"Error scraping Glassdoor: {str(e)}")
        
        return jobs

    def __del__(self):
        """Close browser when done"""
        if hasattr(self, 'driver'):
            self.driver.quit()


@require_http_methods(["GET", "POST"])
def job_search(request):
    """
    View to handle job search functionality
    """
    context = {}
    
    # Check if it's a POST request
    if request.method == "POST":
        # Get search parameters
        role = request.POST.get('role', '')
        location = request.POST.get('location', '')

        # Validate input
        if not role or not location:
            context['error'] = 'Please provide both role and location'
            return render(request, 'prep_app/job_search.html', context)

        # Initialize scraper
        scraper = JobScraper()
        all_jobs = []

        # Use ThreadPoolExecutor for parallel scraping
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Create futures for each job board
            futures = [
                executor.submit(scraper.scrape_linkedin, role, location),
                executor.submit(scraper.scrape_indeed, role, location),
                executor.submit(scraper.scrape_glassdoor, role, location)
            ]
            
            for future in futures:
                try:
                    # Extend all_jobs with results from each future
                    all_jobs.extend(future.result())
                except Exception as e:
                    logging.error(f"Error in scraping: {str(e)}")

        # Sort results by post date (most recent first)
        all_jobs = sorted(all_jobs, key=lambda x: x.get('post_date', '1970-01-01'), reverse=True)
        
        # Add jobs to context
        context['jobs'] = all_jobs
        context['search_params'] = {
            'role': role,
            'location': location
        }

    return render(request, 'prep_app/job_search.html', context)


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

@require_http_methods(["POST"])
def file_upload(request):
    """Minimal upload endpoint used by CV Analysis front-end.
    Accepts file(s) and returns success; does not persist content.
    """
    try:
        uploaded = list(request.FILES.keys())
        if not uploaded:
            return JsonResponse({
                'status': 'error',
                'message': 'No files provided'
            }, status=400)
        # Drain file streams without persisting
        for key, f in request.FILES.items():
            _ = f.read()
        return JsonResponse({'status': 'success', 'files': uploaded})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
