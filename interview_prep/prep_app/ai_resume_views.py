"""
AI Resume Builder Views

Handles the three-page flow for AI Resume Builder:
1. Upload - File upload and job description input
2. Editor - Resume.io style editor with live preview  
3. Download - PDF/DOCX export with analysis summary

Does not make external AI calls - provides integration points for host program.
"""

import json
import logging
from typing import Optional, Dict, Any

from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.urls import reverse
from django.core.exceptions import ValidationError

from .forms import AIResumeUploadForm

try:
    from .services.document_parser import DocumentParser, DocumentParserError
    from .services.ai_integration import AIIntegrationService
    from .services.resume_exporter import ResumeExporter
    from .schemas.ai_resume_schemas import (
        ParsedInputs, AiResult, EditableResume, 
        Analysis, Job, Resume, Contacts, Skills, Education, ExperienceProject, JobKeywords, CustomSection
    )
except ImportError as e:
    # Fallback imports if relative imports fail
    from prep_app.services.document_parser import DocumentParser, DocumentParserError
    from prep_app.services.ai_integration import AIIntegrationService
    from prep_app.services.resume_exporter import ResumeExporter
    from prep_app.schemas.ai_resume_schemas import (
        ParsedInputs, AiResult, EditableResume, 
        Analysis, Job, Resume, Contacts, Skills, Education, ExperienceProject, JobKeywords, CustomSection
    )

logger = logging.getLogger(__name__)


@login_required
def ai_resume_upload(request):
    """
    Page 1 - Upload interface with file validation.
    Handles job information input and resume file upload.
    """
    if request.method == 'POST':
        form = AIResumeUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Extract and validate uploaded file
                resume_file = form.cleaned_data['resume_file']
                extracted_text, file_type = DocumentParser.parse_file(resume_file)
                
                # Create ParsedInputs object
                parsed_inputs = ParsedInputs(
                    job_name=form.cleaned_data['job_name'],
                    job_title=form.cleaned_data['job_title'],
                    job_description_text=form.cleaned_data['job_description'],
                    resume_text=extracted_text,
                    extra_notes=form.cleaned_data.get('extra_notes', '')
                )
                
                # Validate parsed inputs
                parsed_inputs.validate()
                
                # Store in session for next step
                request.session['ai_resume_parsed_inputs'] = {
                    'job_name': parsed_inputs.job_name,
                    'job_title': parsed_inputs.job_title,
                    'job_description_text': parsed_inputs.job_description_text,
                    'resume_text': parsed_inputs.resume_text,
                    'extra_notes': parsed_inputs.extra_notes,
                    'file_type': file_type
                }
                
                # Get AI prompts for host program integration
                system_prompt, user_prompt = AIIntegrationService.get_prompts(parsed_inputs)
                
                # Store prompts for host program
                request.session['ai_resume_prompts'] = {
                    'system': system_prompt,
                    'user': user_prompt
                }
                
                # TODO: Host program should call Gemini API here
                # For now, create a comprehensive AI analysis result
                ai_result = _process_comprehensive_ai_analysis(parsed_inputs)
                
                # Store AI result in session
                request.session['ai_resume_result'] = _serialize_ai_result(ai_result)
                
                messages.success(request, 'Resume uploaded and analyzed successfully!')
                return redirect('ai_resume_editor')
                
            except DocumentParserError as e:
                form.add_error('resume_file', str(e))
                logger.error(f"Document parsing error: {e}")
                
            except ValidationError as e:
                form.add_error(None, str(e))
                logger.error(f"Validation error: {e}")
                
            except Exception as e:
                form.add_error(None, 'An unexpected error occurred. Please try again.')
                logger.error(f"Unexpected error in upload: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
    else:
        form = AIResumeUploadForm()
    
    context = {
        'form': form,
        'page_title': 'AI Resume Builder - Upload'
    }
    
    return render(request, 'ai_resume/page_1_upload.html', context)


@login_required  
def ai_resume_editor(request):
    """
    Page 2 - Resume.io style editor with live A4 preview.
    Handles resume editing and AI Q&A integration.
    """
    # Check if we have AI result from upload
    ai_result_data = request.session.get('ai_resume_result')
    if not ai_result_data:
        messages.error(request, 'Please upload your resume first.')
        return redirect('ai_resume_upload')
    
    try:
        # Deserialize AI result
        ai_result = _deserialize_ai_result(ai_result_data)
        
        # Create editable resume
        editable_resume = EditableResume.from_resume(ai_result.resume)
        
        # Check for current edited resume in session
        current_resume_data = request.session.get('ai_resume_current')
        if current_resume_data:
            editable_resume = _deserialize_editable_resume(current_resume_data)
        
        context = {
            'resume_data': json.dumps(_serialize_editable_resume(editable_resume)),
            'ai_result': json.dumps(_serialize_ai_result(ai_result)),
            'page_title': 'AI Resume Builder - Editor'
        }
        
        return render(request, 'ai_resume/page_2_editor.html', context)
        
    except Exception as e:
        logger.error(f"Error in editor view: {e}")
        messages.error(request, 'Error loading resume editor. Please try uploading again.')
        return redirect('ai_resume_upload')


@login_required
def ai_resume_download(request):
    """
    Page 3 - Download interface with analysis summary.
    Shows final preview and export options.
    """
    # Check if we have resume data
    ai_result_data = request.session.get('ai_resume_result')
    current_resume_data = request.session.get('ai_resume_current')
    parsed_inputs_data = request.session.get('ai_resume_parsed_inputs')
    
    if not ai_result_data or not parsed_inputs_data:
        messages.error(request, 'Please complete the resume building process first.')
        return redirect('ai_resume_upload')
    
    try:
        # Get current resume or fall back to AI version
        if current_resume_data:
            resume_data = _deserialize_editable_resume(current_resume_data)
        else:
            ai_result = _deserialize_ai_result(ai_result_data)
            resume_data = EditableResume.from_resume(ai_result.resume)
        
        # Get analysis and job info
        ai_result = _deserialize_ai_result(ai_result_data)
        parsed_inputs = ParsedInputs(**parsed_inputs_data)
        
        # Generate filename base
        filename_base = _generate_filename_base(resume_data.name, parsed_inputs.job_title)
        
        context = {
            'resume_data': json.dumps(_serialize_editable_resume(resume_data)),
            'analysis': _serialize_analysis(ai_result.analysis),
            'job_info': _serialize_job_info(ai_result.job),
            'filename_base': filename_base,
            'page_title': 'AI Resume Builder - Download'
        }
        
        return render(request, 'ai_resume/page_3_download.html', context)
        
    except Exception as e:
        logger.error(f"Error in download view: {e}")
        messages.error(request, 'Error loading download page.')
        return redirect('ai_resume_editor')


@login_required
@require_POST
def ai_resume_export_pdf(request):
    """Export current resume to PDF format."""
    try:
        resume_data = _get_current_resume_from_session(request)
        parsed_inputs_data = request.session.get('ai_resume_parsed_inputs', {})
        job_title = parsed_inputs_data.get('job_title', '')
        
        return ResumeExporter.export_to_pdf(resume_data, job_title)
        
    except Exception as e:
        logger.error(f"PDF export error: {e}")
        messages.error(request, 'Failed to generate PDF. Please try again.')
        return redirect('ai_resume_download')


@login_required
@require_POST  
def ai_resume_export_docx(request):
    """Export current resume to DOCX format."""
    try:
        resume_data = _get_current_resume_from_session(request)
        parsed_inputs_data = request.session.get('ai_resume_parsed_inputs', {})
        job_title = parsed_inputs_data.get('job_title', '')
        
        return ResumeExporter.export_to_docx(resume_data, job_title)
        
    except Exception as e:
        logger.error(f"DOCX export error: {e}")
        messages.error(request, 'Failed to generate DOCX. Please try again.')
        return redirect('ai_resume_download')


@login_required
@require_POST
@csrf_exempt
def ai_resume_refine(request):
    """
    Handle AI refinement based on user answers to questions_for_user.
    Host program should intercept this and call Gemini API.
    """
    try:
        data = json.loads(request.body)
        user_answers = data.get('user_answers', {})
        current_resume = data.get('current_resume', {})
        
        if not user_answers:
            return JsonResponse({'success': False, 'error': 'No answers provided'})
        
        # Get original inputs
        parsed_inputs_data = request.session.get('ai_resume_parsed_inputs')
        if not parsed_inputs_data:
            return JsonResponse({'success': False, 'error': 'No original data found'})
        
        parsed_inputs = ParsedInputs(**parsed_inputs_data)
        
        # Get refined prompts for host program  
        system_prompt, user_prompt = AIIntegrationService.merge_user_edits(
            parsed_inputs, 
            _deserialize_editable_resume(current_resume),
            user_answers
        )
        
        # Store refined prompts for host program
        request.session['ai_resume_refined_prompts'] = {
            'system': system_prompt,
            'user': user_prompt,
            'user_answers': user_answers
        }
        
        # TODO: Host program should call Gemini API here with refined prompts
        # For now, return the current resume as-is
        return JsonResponse({
            'success': True,
            'resume': current_resume,
            'message': 'Resume updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Refinement error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
@csrf_exempt  
def ai_resume_save(request):
    """Save current resume data to session."""
    try:
        data = json.loads(request.body)
        resume_data = data.get('resume_data', {})
        
        if not resume_data:
            return JsonResponse({'success': False, 'error': 'No resume data provided'})
        
        # Validate and save to session
        editable_resume = _deserialize_editable_resume(resume_data)
        editable_resume.validate()
        
        request.session['ai_resume_current'] = _serialize_editable_resume(editable_resume)
        
        return JsonResponse({'success': True, 'message': 'Resume saved successfully'})
        
    except Exception as e:
        logger.error(f"Save error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
@csrf_exempt
def ai_resume_clear_session(request):
    """Clear AI resume session data."""
    try:
        keys_to_clear = [
            'ai_resume_parsed_inputs',
            'ai_resume_prompts', 
            'ai_resume_result',
            'ai_resume_current',
            'ai_resume_refined_prompts'
        ]
        
        for key in keys_to_clear:
            request.session.pop(key, None)
        
        return JsonResponse({'success': True, 'message': 'Session cleared'})
        
    except Exception as e:
        logger.error(f"Clear session error: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


# Helper functions
def _process_comprehensive_ai_analysis(parsed_inputs: ParsedInputs) -> AiResult:
    """
    4-Step Comprehensive AI Analysis System:
    Step 1: Analyze job description and extract requirements
    Step 2: Analyze resume and extract all details 
    Step 3: Compare resume vs job requirements and tailor content
    Step 4: Generate optimized, ATS-friendly resume data
    """
    import json
    
    print("\n🤖 Starting 4-Step AI Analysis System...")
    
    # STEP 1: Analyze Job Description
    print("\n=== STEP 1: JOB DESCRIPTION ANALYSIS ===")
    job_analysis = _analyze_job_description(parsed_inputs.job_description_text, parsed_inputs.job_title)
    print(f"✅ Job Analysis Complete:")
    print(f"   Title: {job_analysis['title']}")
    print(f"   Seniority: {job_analysis['seniority']}")
    print(f"   Must-have skills: {job_analysis['must_have_skills'][:3]}...") 
    print(f"   Nice-to-have skills: {job_analysis['nice_to_have_skills'][:3]}...")
    print(f"   Total keywords extracted: {len(job_analysis['all_keywords'])}")
    
    # STEP 2: Analyze Resume Content
    print("\n=== STEP 2: RESUME EXTRACTION ANALYSIS ===") 
    resume_analysis = _analyze_resume_content(parsed_inputs.resume_text)
    print(f"✅ Resume Analysis Complete:")
    print(f"   Name: {resume_analysis['personal_info']['name']}")
    print(f"   Email: {resume_analysis['personal_info']['email']}")
    print(f"   Location: {resume_analysis['personal_info']['location']}")
    print(f"   Skills found: {len(resume_analysis['skills']['all_skills'])}")
    print(f"   Experience entries: {len(resume_analysis['experience'])}")
    print(f"   Education entries: {len(resume_analysis['education'])}")
    print(f"   Projects found: {len(resume_analysis['projects'])}")
    
    # STEP 3: Compare and Find Gaps
    print("\n=== STEP 3: RESUME VS JOB COMPARISON ===")
    comparison_analysis = _compare_resume_vs_job(resume_analysis, job_analysis)
    print(f"✅ Comparison Analysis Complete:")
    print(f"   Match score: {comparison_analysis['match_score']}%")
    print(f"   Skills matched: {len(comparison_analysis['matched_skills'])}")
    print(f"   Skills missing: {len(comparison_analysis['missing_skills'])}")
    print(f"   Missing key skills: {comparison_analysis['missing_skills'][:3]}...")
    print(f"   Recommendations: {len(comparison_analysis['recommendations'])}")
    
    # STEP 4: Generate Optimized Resume
    print("\n=== STEP 4: GENERATING OPTIMIZED RESUME ===")
    optimized_resume = _generate_optimized_resume(
        resume_analysis, job_analysis, comparison_analysis, parsed_inputs.job_title
    )
    print(f"✅ Optimized Resume Generated:")
    print(f"   Tailored summary length: {len(optimized_resume['summary'])} chars")
    print(f"   Skills optimized for ATS: {len(optimized_resume['skills']['programming']) + len(optimized_resume['skills']['tools_methodologies'])}")
    print(f"   Experience bullets optimized: {sum(len(exp['bullets']) for exp in optimized_resume['experience'])}")
    print(f"   ATS optimization applied: Keywords integrated")
    
    # Convert to schema objects
    resume_text = parsed_inputs.resume_text
    job_desc = parsed_inputs.job_description_text
    
    # Build schema objects from optimized data
    job_keywords = JobKeywords(
        hard_skills=job_analysis['must_have_skills'] + job_analysis['nice_to_have_skills'],
        soft_skills=job_analysis['soft_skills'],
        tools=job_analysis['tools'],
        certs=job_analysis.get('certifications', []),
        domains=job_analysis.get('domains', [])
    )
    
    job = Job(
        title=job_analysis['title'],
        seniority=job_analysis['seniority'], 
        keywords=job_keywords,
        must_have=job_analysis['must_have_skills'],
        nice_to_have=job_analysis['nice_to_have_skills']
    )
    
    analysis = Analysis(
        coverage_score=comparison_analysis['match_score'],
        missing_keywords=comparison_analysis['missing_skills'][:10],
        recommendations=comparison_analysis['recommendations'][:5]
    )
    
    # Use optimized skills from analysis
    skills = Skills(
        programming=optimized_resume['skills']['programming'],
        database=optimized_resume['skills']['database'], 
        ai_ml_tools=optimized_resume['skills']['ai_ml_tools'],
        tools_methodologies=optimized_resume['skills']['tools_methodologies'],
        soft_skills=optimized_resume['skills']['soft_skills'],
        additional=optimized_resume['skills']['additional']
    )
    
    # Build contacts from optimized data
    contacts = Contacts(
        email=optimized_resume['personal_info']['email'],
        phone=optimized_resume['personal_info']['phone'],
        location=optimized_resume['personal_info']['location'],
        github=optimized_resume['personal_info']['github'],
        website=optimized_resume['personal_info']['website']
    )
    
    # Convert education data
    education_list = []
    for edu in optimized_resume['education']:
        education_list.append(Education(
            degree_bold=edu['degree'],
            institution_bold=edu['institution'], 
            dates_left=edu['dates'],
            location_right=edu['location']
        ))
    
    # Convert experience data
    experience_list = []
    for exp in optimized_resume['experience']:
        experience_list.append(ExperienceProject(
            title_bold_left=exp['title'],
            date_right_nowrap=exp['dates'],
            bullets=exp['bullets']
        ))
    
    # Convert projects data
    projects_list = []
    for proj in optimized_resume['projects']:
        projects_list.append(ExperienceProject(
            title_bold_left=proj['title'],
            date_right_nowrap=proj['dates'],
            bullets=proj['bullets']
        ))
    
    resume = Resume(
        name=optimized_resume['personal_info']['name'],
        role=optimized_resume['personal_info']['title'],
        contacts=contacts,
        summary=optimized_resume['summary'],
        skills=skills,
        education=education_list,
        experience=experience_list,
        projects=projects_list
    )
    
    # Generate intelligent questions based on gaps
    questions = []
    for skill in comparison_analysis['missing_skills'][:3]:
        questions.append(f"Do you have experience with {skill}? If so, please provide specific examples and duration.")
    
    if comparison_analysis['match_score'] < 70:
        questions.append(f"Can you provide more details about your experience that relates to {job_analysis['title']}?")
    
    print(f"\n🎯 Final AI Analysis Summary:")
    print(f"   Resume optimized for: {job_analysis['title']}")
    print(f"   ATS match score: {comparison_analysis['match_score']}%")
    print(f"   Skills alignment: {len(comparison_analysis['matched_skills'])} matched, {len(comparison_analysis['missing_skills'])} missing")
    print(f"   Questions generated: {len(questions)}")
    print(f"   Ready for editor! ✨")
    
    return AiResult(
        job=job,
        analysis=analysis,
        resume=resume,
        questions_for_user=questions[:3]  # Limit to 3 questions
    )


# === 4-STEP AI ANALYSIS FUNCTIONS ===

def _analyze_job_description(job_description: str, job_title: str = None) -> dict:
    """
    STEP 1: Comprehensive Job Description Analysis
    
    Analyzes job description to extract:
    - Job title and seniority level
    - Required skills (must-have vs nice-to-have)
    - Technical keywords for ATS optimization
    - Soft skills and methodologies
    - Company culture indicators
    """
    import re
    
    job_desc = job_description.lower().strip()
    if not job_desc:
        return _get_default_job_analysis(job_title)
    
    # Extract job title and seniority
    title = job_title or _extract_job_title_advanced(job_description)
    seniority = _extract_seniority_advanced(job_desc)
    
    # Extract skills with context
    must_have_skills = _extract_must_have_skills_advanced(job_desc)
    nice_to_have_skills = _extract_nice_to_have_skills_advanced(job_desc)
    
    # Extract technical categories
    programming_languages = _extract_programming_languages(job_desc)
    databases = _extract_databases(job_desc)
    tools_frameworks = _extract_tools_frameworks(job_desc)
    cloud_platforms = _extract_cloud_platforms(job_desc)
    soft_skills = _extract_soft_skills_from_job(job_desc)
    
    # Extract experience requirements
    years_required = _extract_years_experience(job_desc)
    education_required = _extract_education_requirements(job_desc)
    
    # Build comprehensive keyword list for ATS
    all_keywords = (must_have_skills + nice_to_have_skills + 
                   programming_languages + databases + tools_frameworks + 
                   cloud_platforms + soft_skills)
    
    return {
        'title': title,
        'seniority': seniority,
        'must_have_skills': must_have_skills,
        'nice_to_have_skills': nice_to_have_skills,
        'programming_languages': programming_languages,
        'databases': databases,
        'tools_frameworks': tools_frameworks,
        'cloud_platforms': cloud_platforms,
        'soft_skills': soft_skills,
        'tools': tools_frameworks + cloud_platforms,
        'years_required': years_required,
        'education_required': education_required,
        'all_keywords': all_keywords,
        'keyword_density_target': len(all_keywords) * 2  # Target for ATS optimization
    }


def _analyze_resume_content(resume_text: str) -> dict:
    """
    STEP 2: Comprehensive Resume Content Analysis
    
    Extracts all resume details including:
    - Personal information (name, contact, location)
    - Professional summary/objective
    - Technical and soft skills
    - Work experience with details
    - Education background
    - Projects and achievements
    - Certifications and languages
    """
    import re
    
    if not resume_text:
        return _get_empty_resume_analysis()
    
    # Personal Information Extraction
    personal_info = {
        'name': _extract_name_from_resume(resume_text),
        'email': _extract_email_from_resume(resume_text),
        'phone': _extract_phone_from_resume(resume_text),
        'location': _extract_location_from_resume(resume_text),
        'github': _extract_github_from_resume(resume_text),
        'linkedin': _extract_linkedin_from_resume(resume_text),
        'website': _extract_website_from_resume(resume_text),
        'title': _extract_current_title_from_resume(resume_text)
    }
    
    # Skills Analysis  
    skills_analysis = {
        'programming': _extract_programming_skills_from_resume(resume_text),
        'database': _extract_database_skills_from_resume(resume_text),
        'ai_ml_tools': _extract_ai_ml_skills_from_resume(resume_text),
        'tools_methodologies': _extract_tools_methodologies_from_resume(resume_text),
        'soft_skills': _extract_soft_skills_from_resume(resume_text),
        'additional': _extract_additional_skills_from_resume(resume_text),
        'all_skills': []  # Will be populated below
    }
    skills_analysis['all_skills'] = (skills_analysis['programming'] + 
                                   skills_analysis['database'] +
                                   skills_analysis['ai_ml_tools'] +
                                   skills_analysis['tools_methodologies'] +
                                   skills_analysis['soft_skills'] +
                                   skills_analysis['additional'])
    
    # Experience Analysis
    experience = _extract_experience_detailed_from_resume(resume_text)
    
    # Education Analysis
    education = _extract_education_detailed_from_resume(resume_text)
    
    # Projects Analysis
    projects = _extract_projects_detailed_from_resume(resume_text)
    
    # Summary/Objective
    summary = _extract_summary_from_resume(resume_text)
    
    # Additional sections
    certifications = _extract_certifications_from_resume(resume_text)
    languages = _extract_languages_from_resume(resume_text)
    
    return {
        'personal_info': personal_info,
        'summary': summary,
        'skills': skills_analysis,
        'experience': experience,
        'education': education,
        'projects': projects,
        'certifications': certifications,
        'languages': languages,
        'total_experience_years': _calculate_total_experience_years(experience),
        'education_level': _determine_education_level(education)
    }


def _compare_resume_vs_job(resume_analysis: dict, job_analysis: dict) -> dict:
    """
    STEP 3: Resume vs Job Requirements Comparison
    
    Compares resume against job requirements to identify:
    - Skills matches and gaps
    - Experience level alignment
    - Education requirements fulfillment
    - ATS keyword optimization opportunities
    - Specific recommendations for improvement
    """
    
    # Skills matching analysis
    resume_skills = set(skill.lower() for skill in resume_analysis['skills']['all_skills'])
    job_skills = set(skill.lower() for skill in job_analysis['all_keywords'])
    
    matched_skills = list(resume_skills.intersection(job_skills))
    missing_skills = list(job_skills - resume_skills)
    extra_skills = list(resume_skills - job_skills)
    
    # Calculate match percentages
    skills_match_score = len(matched_skills) / len(job_skills) * 100 if job_skills else 0
    
    # Experience level matching
    experience_match = _compare_experience_levels(
        resume_analysis['total_experience_years'],
        job_analysis['years_required']
    )
    
    # Education matching
    education_match = _compare_education_levels(
        resume_analysis['education_level'], 
        job_analysis['education_required']
    )
    
    # Overall match score (weighted)
    overall_match_score = (
        skills_match_score * 0.6 +        # Skills are 60% of match
        experience_match * 0.3 +          # Experience is 30% of match  
        education_match * 0.1             # Education is 10% of match
    )
    
    # Generate specific recommendations
    recommendations = _generate_tailoring_recommendations(
        resume_analysis, job_analysis, matched_skills, missing_skills
    )
    
    # ATS optimization suggestions
    ats_suggestions = _generate_ats_optimization_suggestions(
        resume_analysis, job_analysis, missing_skills
    )
    
    return {
        'match_score': round(overall_match_score, 1),
        'skills_match_score': round(skills_match_score, 1),
        'experience_match_score': round(experience_match, 1),
        'education_match_score': round(education_match, 1),
        'matched_skills': matched_skills,
        'missing_skills': missing_skills[:15],  # Top 15 missing
        'extra_skills': extra_skills,
        'recommendations': recommendations,
        'ats_suggestions': ats_suggestions,
        'priority_improvements': _identify_priority_improvements(missing_skills, job_analysis)
    }


def _generate_optimized_resume(resume_analysis: dict, job_analysis: dict, 
                              comparison_analysis: dict, target_job_title: str) -> dict:
    """
    STEP 4: Generate ATS-Optimized, Tailored Resume
    
    Creates an optimized resume version that:
    - Integrates missing keywords naturally
    - Tailors summary for the specific role
    - Optimizes bullet points with job-relevant achievements
    - Reorganizes skills for better ATS scanning
    - Enhances experience descriptions with relevant context
    """
    
    # Optimize personal information
    optimized_personal = _optimize_personal_info(
        resume_analysis['personal_info'], target_job_title
    )
    
    # Generate tailored summary
    optimized_summary = _generate_tailored_summary(
        resume_analysis, job_analysis, target_job_title
    )
    
    # Optimize skills organization for ATS
    optimized_skills = _optimize_skills_for_ats(
        resume_analysis['skills'], job_analysis, comparison_analysis['missing_skills']
    )
    
    # Enhance experience descriptions
    optimized_experience = _optimize_experience_descriptions(
        resume_analysis['experience'], job_analysis, comparison_analysis['missing_skills']
    )
    
    # Optimize education formatting
    optimized_education = _optimize_education_for_job(
        resume_analysis['education'], job_analysis
    )
    
    # Enhance projects with job-relevant context
    optimized_projects = _optimize_projects_for_job(
        resume_analysis['projects'], job_analysis, comparison_analysis['missing_skills']
    )
    
    return {
        'personal_info': optimized_personal,
        'summary': optimized_summary,
        'skills': optimized_skills,
        'experience': optimized_experience,
        'education': optimized_education,
        'projects': optimized_projects,
        'ats_score_estimated': _calculate_ats_score(job_analysis, optimized_skills),
        'optimization_applied': True,
        'keywords_integrated': len(comparison_analysis['missing_skills'][:10])
    }


# === INTELLIGENT PARSING HELPER FUNCTIONS ===

def _extract_keywords_from_job_desc(job_desc: str) -> 'JobKeywords':
    """Extract skills and keywords from job description."""
    text = job_desc.lower()
    
    # Technical skills patterns
    programming_skills = []
    for skill in ['python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'php', 'ruby', 'swift', 'kotlin', 'typescript', 'react', 'angular', 'vue', 'django', 'flask', 'spring', 'express']:
        if skill in text:
            programming_skills.append(skill.title())
    
    database_skills = []
    for db in ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle', 'sqlite']:
        if db in text:
            database_skills.append(db.upper() if db == 'sql' else db.title())
    
    cloud_tools = []
    for tool in ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'git', 'jenkins', 'ci/cd', 'devops']:
        if tool in text:
            cloud_tools.append(tool.upper() if tool in ['aws', 'gcp'] else tool.title())
    
    return JobKeywords(
        hard_skills=programming_skills[:10],
        soft_skills=['Communication', 'Problem Solving', 'Teamwork', 'Leadership'],
        tools=cloud_tools[:8],
        certs=[],
        domains=[]
    )

def _extract_job_title(job_desc: str) -> str:
    """Extract job title from job description."""
    lines = job_desc.split('\n')
    if lines:
        first_line = lines[0].strip()
        if len(first_line) < 100 and any(word in first_line.lower() for word in ['engineer', 'developer', 'analyst', 'manager', 'lead', 'senior']):
            return first_line
    return "Software Engineer"

def _extract_seniority_level(job_desc: str) -> str:
    """Extract seniority level from job description."""
    text = job_desc.lower()
    if 'senior' in text or '5+' in text or '5 years' in text:
        return "Senior"
    elif 'junior' in text or 'entry' in text or '0-2' in text:
        return "Junior" 
    else:
        return "Mid-Level"

def _extract_must_have_skills(job_desc: str) -> list:
    """Extract must-have skills from job description."""
    must_haves = []
    text = job_desc.lower()
    
    # Look for experience patterns
    import re
    experience_matches = re.findall(r'(\d+)\+?\s*years?\s+(?:of\s+)?(?:experience\s+)?(?:in\s+|with\s+)?([a-zA-Z\s/+#]+)', text)
    for years, skill in experience_matches[:3]:
        must_haves.append(f"{years}+ years {skill.strip()}")
    
    # Look for degree requirements
    if 'degree' in text or 'bachelor' in text or 'masters' in text:
        must_haves.append("CS Degree or equivalent")
    
    return must_haves[:5]

def _extract_nice_to_have_skills(job_desc: str) -> list:
    """Extract nice-to-have skills."""
    nice_to_have = []
    text = job_desc.lower()
    
    for skill in ['aws', 'azure', 'docker', 'kubernetes', 'machine learning', 'ai', 'agile', 'scrum']:
        if skill in text:
            nice_to_have.append(skill.title())
    
    return nice_to_have[:5]

def _extract_name_from_resume(resume_text: str) -> str:
    """Extract name from resume text with improved logic."""
    lines = resume_text.split('\n')
    
    # Look for patterns that indicate a name
    for i, line in enumerate(lines[:10]):  # Check first 10 lines
        line = line.strip()
        if not line:
            continue
            
        # Skip common resume headers
        if any(header in line.lower() for header in ['resume', 'curriculum vitae', 'cv', 'profile']):
            continue
            
        # Skip contact info lines
        if any(contact in line for contact in ['@', 'phone', 'email', 'tel:', 'mobile', '+', '(', ')', '-', 'linkedin', 'github']):
            continue
            
        # Look for name patterns
        words = line.split()
        if 2 <= len(words) <= 4:  # Names typically 2-4 words
            # Check if it looks like a name (no numbers, reasonable length)
            if (not any(char.isdigit() for char in line) and 
                len(line) >= 5 and len(line) <= 50 and
                all(word.isalpha() or word.replace('.', '').isalpha() for word in words)):
                # Additional validation - names usually have capital letters
                if any(word[0].isupper() for word in words if word):
                    return line
                    
    # If no clear name found, try first non-empty line that's not obviously contact info
    for line in lines[:5]:
        line = line.strip()
        if (line and len(line) > 3 and 
            not any(char in line for char in ['@', '(', ')', '+', '-']) and
            not line.lower().startswith(('resume', 'cv', 'curriculum'))):
            return line
            
    return "Your Name"

def _extract_contacts_from_resume(resume_text: str) -> 'Contacts':
    """Extract contact information from resume."""
    import re
    
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_text)
    phone_match = re.search(r'[\+]?[1-9]?[0-9]{7,12}', resume_text)
    github_match = re.search(r'github\.com/([A-Za-z0-9_-]+)', resume_text, re.IGNORECASE)
    
    return Contacts(
        email_left=email_match.group(0) if email_match else "your.email@example.com",
        phone_center=phone_match.group(0) if phone_match else "+44 xxxx xxx xxx",
        location_right="City, Country",  # Hard to extract reliably
        github_left=github_match.group(0) if github_match else "",
        website_right=""
    )

def _extract_skills_from_resume(resume_text: str) -> 'Skills':
    """Extract skills from resume text."""
    text = resume_text.lower()
    
    programming = []
    for skill in ['python', 'javascript', 'java', 'c++', 'react', 'angular', 'django', 'flask', 'node.js']:
        if skill.replace('.', '') in text.replace('.', ''):
            programming.append(skill.title() if '.' not in skill else skill)
    
    database = []
    for db in ['sql', 'mysql', 'postgresql', 'mongodb', 'redis']:
        if db in text:
            database.append(db.upper() if db == 'sql' else db.title())
    
    return Skills(
        programming=programming[:8] if programming else ["Python", "JavaScript"],
        database=database[:5] if database else ["SQL"],
        ai_ml_tools=[],
        tools_methodologies=[],
        soft_skills=[],
        additional=[]
    )

def _extract_or_generate_summary(resume_text: str, job_title: str) -> str:
    """Extract existing summary or generate one from resume content."""
    lines = resume_text.split('\n')
    
    # Look for existing summary/objective section
    for i, line in enumerate(lines):
        if any(word in line.lower() for word in ['summary', 'objective', 'profile', 'about']):
            # Get next few lines as summary
            summary_lines = []
            for j in range(i+1, min(i+4, len(lines))):
                if lines[j].strip():
                    summary_lines.append(lines[j].strip())
            if summary_lines:
                return ' '.join(summary_lines)
    
    # Generate basic summary if not found
    return f"Experienced professional seeking opportunities in {job_title or 'software development'}. Skilled in various technologies with a passion for creating innovative solutions."

def _extract_education_from_resume(resume_text: str) -> list:
    """Extract education information."""
    # Simple extraction - look for degree patterns
    import re
    
    degree_patterns = [
        r'(bachelor|bsc|ba|bs|master|msc|ma|ms|phd|doctorate)[\s\w]*(?:in|of)\s+([^\n]+)',
        r'(computer science|engineering|mathematics|business)',
    ]
    
    education_list = []
    for pattern in degree_patterns:
        matches = re.findall(pattern, resume_text, re.IGNORECASE)
        for match in matches[:2]:  # Limit to 2 entries
            if isinstance(match, tuple):
                degree = f"{match[0]} {match[1]}" if len(match) > 1 else match[0]
            else:
                degree = match
            
            education_list.append(Education(
                degree_bold=degree.title(),
                institution_bold="University Name",
                dates_left="2018 - 2022",
                location_right="City, Country"
            ))
    
    return education_list[:2] if education_list else [Education(
        degree_bold="Your Degree",
        institution_bold="Your University", 
        dates_left="Start - End",
        location_right="City, Country"
    )]

def _extract_experience_from_resume(resume_text: str) -> list:
    """Extract work experience."""
    # This is a simplified extraction
    lines = resume_text.split('\n')
    experience_entries = []
    
    current_entry = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for job titles or company names (heuristic)
        if any(word in line.lower() for word in ['engineer', 'developer', 'analyst', 'manager', 'intern']):
            if current_entry:
                experience_entries.append(current_entry)
            current_entry = ExperienceProject(
                title_bold_left=line[:50],  # Truncate if too long
                date_right_nowrap="2020 - Present",
                bullets=[]
            )
        elif current_entry and line.startswith(('•', '-', '*')) and len(line) > 10:
            # This looks like a bullet point
            bullet = line.lstrip('•-* ').strip()
            if bullet:
                current_entry.bullets.append(bullet[:200])  # Limit length
    
    if current_entry:
        experience_entries.append(current_entry)
    
    return experience_entries[:3] if experience_entries else [ExperienceProject(
        title_bold_left="Your Job Title",
        date_right_nowrap="Start - End",
        bullets=["Key achievement or responsibility"]
    )]

def _extract_projects_from_resume(resume_text: str) -> list:
    """Extract projects information."""
    # Similar to experience but look for project keywords
    return [ExperienceProject(
        title_bold_left="Your Project Name", 
        date_right_nowrap="Year",
        bullets=["Project description and achievements"]
    )]

def _calculate_coverage_score(resume_text: str, job_desc: str, keywords: 'JobKeywords') -> float:
    """Calculate how well resume matches job description."""
    resume_lower = resume_text.lower()
    job_lower = job_desc.lower()
    
    all_skills = keywords.hard_skills + keywords.tools
    if not all_skills:
        return 0.5  # Default score
    
    matches = sum(1 for skill in all_skills if skill.lower() in resume_lower)
    return min(1.0, matches / len(all_skills))

def _find_missing_keywords(resume_text: str, keywords: 'JobKeywords') -> list:
    """Find keywords from job that are missing in resume."""
    resume_lower = resume_text.lower()
    missing = []
    
    for skill in keywords.hard_skills + keywords.tools:
        if skill.lower() not in resume_lower:
            missing.append(skill)
    
    return missing

def _generate_recommendations(missing_keywords: list, coverage_score: float) -> list:
    """Generate improvement recommendations."""
    recommendations = []
    
    if coverage_score < 0.6:
        recommendations.append("Consider adding more relevant technical skills mentioned in the job description")
    
    if missing_keywords:
        recommendations.append(f"Include experience with: {', '.join(missing_keywords[:3])}")
    
    recommendations.extend([
        "Add quantifiable achievements and metrics to your experience",
        "Ensure your summary aligns with the job requirements",
        "Consider adding relevant certifications or training"
    ])
    
    return recommendations

def _generate_questions_for_missing_skills(missing_keywords: list, resume_text: str) -> list:
    """Generate questions about missing skills."""
    questions = []
    
    for skill in missing_keywords[:3]:
        questions.append(f"Do you have experience with {skill}? Please provide details.")
    
    return questions


def _get_current_resume_from_session(request) -> EditableResume:
    """Get current resume from session or create from AI result."""
    current_resume_data = request.session.get('ai_resume_current')
    
    if current_resume_data:
        return _deserialize_editable_resume(current_resume_data)
    
    # Fall back to AI result
    ai_result_data = request.session.get('ai_resume_result')
    if ai_result_data:
        ai_result = _deserialize_ai_result(ai_result_data)
        return EditableResume.from_resume(ai_result.resume)
    
    raise ValueError("No resume data found in session")


def _generate_filename_base(name: str, job_title: str) -> str:
    """Generate base filename for exports."""
    clean_name = ''.join(c for c in (name or 'Resume') if c.isalnum() or c in ' -_').strip()
    clean_name = clean_name.replace(' ', '_')
    
    clean_job = ''.join(c for c in (job_title or '') if c.isalnum() or c in ' -_').strip()
    clean_job = clean_job.replace(' ', '_')
    
    if clean_job:
        return f"{clean_name}_{clean_job}_Resume"
    else:
        return f"{clean_name}_Resume"


# Serialization helpers
def _serialize_ai_result(ai_result: AiResult) -> dict:
    """Serialize AiResult to dict for JSON storage."""
    return {
        'job': {
            'title': ai_result.job.title,
            'seniority': ai_result.job.seniority,
            'keywords': {
                'hard_skills': ai_result.job.keywords.hard_skills,
                'soft_skills': ai_result.job.keywords.soft_skills,
                'tools': ai_result.job.keywords.tools,
                'certs': ai_result.job.keywords.certs,
                'domains': ai_result.job.keywords.domains
            },
            'must_have': ai_result.job.must_have,
            'nice_to_have': ai_result.job.nice_to_have
        },
        'analysis': {
            'coverage_score': ai_result.analysis.coverage_score,
            'missing_keywords': ai_result.analysis.missing_keywords,
            'recommendations': ai_result.analysis.recommendations
        },
        'resume': _serialize_resume(ai_result.resume),
        'questions_for_user': ai_result.questions_for_user
    }


def _deserialize_ai_result(data: dict) -> AiResult:
    """Deserialize dict to AiResult."""
    return AiResult.from_dict(data)


def _serialize_editable_resume(resume: EditableResume) -> dict:
    """Serialize EditableResume to dict compatible with live preview template."""
    # Convert skills lists to comma-separated strings for live template compatibility
    def list_to_string(skill_list):
        if isinstance(skill_list, list):
            return ', '.join(skill_list) if skill_list else ''
        return str(skill_list) if skill_list else ''
    
    # Handle education - use first education entry for single education format
    education_data = {'degree': '', 'institution': '', 'dates': '', 'loc': ''}
    if resume.education and len(resume.education) > 0:
        first_edu = resume.education[0]
        education_data = {
            'degree': first_edu.degree_bold,
            'institution': first_edu.institution_bold, 
            'dates': first_edu.dates_left,
            'loc': first_edu.location_right
        }
    
    # Convert experience and projects to simple format
    experience_list = []
    for exp in resume.experience:
        bullets_text = '\n'.join(exp.bullets) if isinstance(exp.bullets, list) else str(exp.bullets)
        experience_list.append({
            'title': exp.title_bold_left,
            'date': exp.date_right_nowrap,
            'bullets': bullets_text
        })
    
    projects_list = []
    for proj in resume.projects:
        bullets_text = '\n'.join(proj.bullets) if isinstance(proj.bullets, list) else str(proj.bullets)
        projects_list.append({
            'title': proj.title_bold_left,
            'date': proj.date_right_nowrap,
            'bullets': bullets_text
        })
    
    return {
        'name': resume.name,
        'role': resume.role,
        'email': resume.contacts.email,
        'phone': resume.contacts.phone,
        'location': resume.contacts.location,
        'github': resume.contacts.github,
        'website': resume.contacts.website,
        'summary': resume.summary,
        'skills': {
            'programming': list_to_string(resume.skills.programming),
            'database': list_to_string(resume.skills.database),
            'aiml': list_to_string(resume.skills.ai_ml_tools),
            'tools': list_to_string(resume.skills.tools_methodologies),
            'soft': list_to_string(resume.skills.soft_skills),
            'additional': list_to_string(resume.skills.additional)
        },
        'education': education_data,
        'experience': experience_list,
        'projects': projects_list,
        'custom_sections': [
            {
                'heading': section.heading,
                'bullets': section.bullets
            }
            for section in resume.custom_sections
        ]
    }


def _deserialize_editable_resume(data: dict) -> EditableResume:
    """Deserialize dict to EditableResume."""
    
    contacts = Contacts(**data.get('contacts', {}))
    skills = Skills(**data.get('skills', {}))
    
    education = [Education(**edu) for edu in data.get('education', [])]
    experience = [ExperienceProject(**exp) for exp in data.get('experience', [])]
    projects = [ExperienceProject(**proj) for proj in data.get('projects', [])]
    custom_sections = [CustomSection(**section) for section in data.get('custom_sections', [])]
    
    return EditableResume(
        name=data.get('name', ''),
        role=data.get('role', ''),
        contacts=contacts,
        summary=data.get('summary', ''),
        skills=skills,
        education=education,
        experience=experience,
        projects=projects,
        custom_sections=custom_sections
    )


def _serialize_resume(resume: Resume) -> dict:
    """Serialize Resume to dict for AiResult schema compatibility."""
    return {
        'name': resume.name,
        'role': resume.role,
        'contacts': {
            'email': resume.contacts.email,
            'phone': resume.contacts.phone,
            'location': resume.contacts.location,
            'github': resume.contacts.github,
            'website': resume.contacts.website
        },
        'summary': resume.summary,
        'skills': {
            'programming': resume.skills.programming,
            'database': resume.skills.database,
            'ai_ml_tools': resume.skills.ai_ml_tools,
            'tools_methodologies': resume.skills.tools_methodologies,
            'soft_skills': resume.skills.soft_skills,
            'additional': resume.skills.additional
        },
        'education': [
            {
                'degree_bold': edu.degree_bold,
                'institution_bold': edu.institution_bold,
                'dates_left': edu.dates_left,
                'location_right': edu.location_right
            }
            for edu in resume.education
        ],
        'experience': [
            {
                'title_bold_left': exp.title_bold_left,
                'date_right_nowrap': exp.date_right_nowrap,
                'bullets': exp.bullets
            }
            for exp in resume.experience
        ],
        'projects': [
            {
                'title_bold_left': proj.title_bold_left,
                'date_right_nowrap': proj.date_right_nowrap,
                'bullets': proj.bullets
            }
            for proj in resume.projects
        ]
    }

def _serialize_resume_for_editor(resume: Resume) -> dict:
    """Serialize Resume to dict compatible with live preview template format."""
    # Convert skills lists to comma-separated strings for live template compatibility
    def list_to_string(skill_list):
        if isinstance(skill_list, list):
            return ', '.join(skill_list) if skill_list else ''
        return str(skill_list) if skill_list else ''
    
    # Handle education - use first education entry for single education format
    education_data = {'degree': '', 'institution': '', 'dates': '', 'loc': ''}
    if resume.education and len(resume.education) > 0:
        first_edu = resume.education[0]
        education_data = {
            'degree': first_edu.degree_bold,
            'institution': first_edu.institution_bold, 
            'dates': first_edu.dates_left,
            'loc': first_edu.location_right
        }
    
    # Convert experience and projects to simple format
    experience_list = []
    for exp in resume.experience:
        # Convert bullets list to newline-separated string
        bullets_text = '\n'.join(exp.bullets) if isinstance(exp.bullets, list) else str(exp.bullets)
        experience_list.append({
            'title': exp.title_bold_left,
            'date': exp.date_right_nowrap,
            'bullets': bullets_text
        })
    
    projects_list = []
    for proj in resume.projects:
        # Convert bullets list to newline-separated string
        bullets_text = '\n'.join(proj.bullets) if isinstance(proj.bullets, list) else str(proj.bullets)
        projects_list.append({
            'title': proj.title_bold_left,
            'date': proj.date_right_nowrap,
            'bullets': bullets_text
        })
    
    return {
        'name': resume.name,
        'role': resume.role,
        'email': resume.contacts.email,
        'phone': resume.contacts.phone,
        'location': resume.contacts.location,
        'github': resume.contacts.github,
        'website': resume.contacts.website,
        'summary': resume.summary,
        'skills': {
            'programming': list_to_string(resume.skills.programming),
            'database': list_to_string(resume.skills.database),
            'aiml': list_to_string(resume.skills.ai_ml_tools),
            'tools': list_to_string(resume.skills.tools_methodologies),
            'soft': list_to_string(resume.skills.soft_skills),
            'additional': list_to_string(resume.skills.additional)
        },
        'education': education_data,
        'experience': experience_list,
        'projects': projects_list
    }


def _serialize_analysis(analysis: Analysis) -> dict:
    """Serialize Analysis to dict."""
    return {
        'coverage_score': analysis.coverage_score,
        'missing_keywords': analysis.missing_keywords,
        'recommendations': analysis.recommendations
    }


def _serialize_job_info(job: Job) -> dict:
    """Serialize Job to dict."""
    return {
        'title': job.title,
        'name': job.title,  # Using title as name for template
        'seniority': job.seniority,
        'keywords': {
            'must_have': job.must_have,
            'hard_skills': job.keywords.hard_skills,
            'soft_skills': job.keywords.soft_skills,
            'tools': job.keywords.tools,
            'certs': job.keywords.certs,
            'domains': job.keywords.domains
        }
    }


# === COMPREHENSIVE HELPER FUNCTIONS FOR 4-STEP ANALYSIS ===

# STEP 1 HELPERS: Job Description Analysis
def _get_default_job_analysis(job_title: str = None) -> dict:
    """Return default job analysis when job description is empty."""
    return {
        'title': job_title or 'Software Engineer',
        'seniority': 'Mid-Level',
        'must_have_skills': ['Programming', 'Problem Solving'],
        'nice_to_have_skills': ['Team Collaboration', 'Communication'],
        'programming_languages': ['Python', 'JavaScript'],
        'databases': ['SQL'],
        'tools_frameworks': ['Git'],
        'cloud_platforms': [],
        'soft_skills': ['Communication', 'Problem Solving'],
        'tools': ['Git'],
        'years_required': '2-3',
        'education_required': 'Bachelor\'s Degree',
        'all_keywords': ['Programming', 'Problem Solving', 'Python', 'JavaScript', 'SQL', 'Git'],
        'keyword_density_target': 12
    }

def _extract_job_title_advanced(job_description: str) -> str:
    """Extract job title with advanced parsing."""
    import re
    lines = job_description.split('\n')
    
    # Look for title patterns in first few lines
    for i, line in enumerate(lines[:5]):
        line = line.strip()
        if not line:
            continue
            
        # Common title patterns
        title_patterns = [
            r'(?i)(senior|junior|lead|principal)\s+(software|web|data|machine learning|ai|full stack|backend|frontend|devops)\s+(engineer|developer|analyst|scientist)',
            r'(?i)(software|web|data|machine learning|ai|full stack|backend|frontend|devops)\s+(engineer|developer|analyst|scientist)',
            r'(?i)(senior|junior|lead|principal)\s+(python|javascript|react|node|django|flask)\s+(developer|engineer)',
            r'(?i)(python|javascript|react|node|django|flask)\s+(developer|engineer)'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(0).title()
    
    return "Software Engineer"

def _extract_seniority_advanced(job_desc: str) -> str:
    """Extract seniority level with advanced parsing."""
    import re
    
    # Senior indicators
    if any(word in job_desc for word in ['senior', 'lead', 'principal', 'staff', '5+ years', '6+ years', '7+ years']):
        return "Senior"
    # Junior indicators  
    elif any(word in job_desc for word in ['junior', 'entry', 'graduate', '0-2 years', 'new grad']):
        return "Junior"
    # Mid-level indicators
    elif any(word in job_desc for word in ['2-4 years', '3-5 years', '2+ years', '3+ years']):
        return "Mid-Level"
    
    return "Mid-Level"

def _extract_must_have_skills_advanced(job_desc: str) -> list:
    """Extract must-have skills from job description."""
    import re
    
    must_have_skills = []
    
    # Look for explicit must-have sections
    must_have_patterns = [
        r'(?i)required\s*:?\s*([^\n]+)',
        r'(?i)must\s+have\s*:?\s*([^\n]+)',
        r'(?i)essential\s*:?\s*([^\n]+)',
        r'(?i)minimum\s+requirements\s*:?\s*([^\n]+)'
    ]
    
    for pattern in must_have_patterns:
        matches = re.findall(pattern, job_desc)
        for match in matches:
            skills = _extract_skills_from_text(match)
            must_have_skills.extend(skills)
    
    # Look for common technical must-haves
    tech_skills = _extract_programming_languages(job_desc) + _extract_databases(job_desc)
    must_have_skills.extend(tech_skills[:5])  # Top 5 tech skills
    
    return list(set(must_have_skills))[:10]  # Remove duplicates, limit to 10

def _extract_nice_to_have_skills_advanced(job_desc: str) -> list:
    """Extract nice-to-have skills from job description."""
    import re
    
    nice_to_have_skills = []
    
    # Look for explicit nice-to-have sections
    nice_patterns = [
        r'(?i)preferred\s*:?\s*([^\n]+)',
        r'(?i)nice\s+to\s+have\s*:?\s*([^\n]+)',
        r'(?i)bonus\s*:?\s*([^\n]+)',
        r'(?i)additional\s*:?\s*([^\n]+)'
    ]
    
    for pattern in nice_patterns:
        matches = re.findall(pattern, job_desc)
        for match in matches:
            skills = _extract_skills_from_text(match)
            nice_to_have_skills.extend(skills)
    
    # Add additional tools and frameworks
    tools = _extract_tools_frameworks(job_desc) + _extract_cloud_platforms(job_desc)
    nice_to_have_skills.extend(tools)
    
    return list(set(nice_to_have_skills))[:10]

def _extract_programming_languages(text: str) -> list:
    """Extract programming languages from text."""
    languages = ['python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'php', 'ruby', 
                'swift', 'kotlin', 'typescript', 'scala', 'r', 'matlab', 'perl', 'objective-c']
    
    found_languages = []
    text_lower = text.lower()
    
    for lang in languages:
        if lang in text_lower:
            # Format properly
            if lang == 'c++':
                found_languages.append('C++')
            elif lang == 'c#':
                found_languages.append('C#')
            elif lang == 'objective-c':
                found_languages.append('Objective-C')
            else:
                found_languages.append(lang.title())
    
    return found_languages

def _extract_databases(text: str) -> list:
    """Extract database technologies from text."""
    databases = ['mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle', 
                'sqlite', 'cassandra', 'dynamodb', 'sql server', 'mariadb']
    
    found_dbs = []
    text_lower = text.lower()
    
    for db in databases:
        if db in text_lower:
            # Format properly
            if db == 'mysql':
                found_dbs.append('MySQL')
            elif db == 'postgresql':
                found_dbs.append('PostgreSQL')
            elif db == 'mongodb':
                found_dbs.append('MongoDB')
            elif db == 'elasticsearch':
                found_dbs.append('Elasticsearch')
            elif db == 'dynamodb':
                found_dbs.append('DynamoDB')
            elif db == 'sql server':
                found_dbs.append('SQL Server')
            else:
                found_dbs.append(db.title())
    
    # Always include SQL if any database is mentioned
    if found_dbs and 'SQL' not in found_dbs:
        found_dbs.append('SQL')
    
    return found_dbs

def _extract_tools_frameworks(text: str) -> list:
    """Extract tools and frameworks from text."""
    tools = ['react', 'angular', 'vue', 'django', 'flask', 'spring', 'express', 'git', 
            'docker', 'kubernetes', 'jenkins', 'terraform', 'ansible', 'webpack', 'babel']
    
    found_tools = []
    text_lower = text.lower()
    
    for tool in tools:
        if tool in text_lower:
            found_tools.append(tool.title())
    
    return found_tools

def _extract_cloud_platforms(text: str) -> list:
    """Extract cloud platforms from text."""
    clouds = ['aws', 'azure', 'gcp', 'google cloud', 'amazon web services', 'microsoft azure']
    
    found_clouds = []
    text_lower = text.lower()
    
    if 'aws' in text_lower or 'amazon web services' in text_lower:
        found_clouds.append('AWS')
    if 'azure' in text_lower or 'microsoft azure' in text_lower:
        found_clouds.append('Azure')
    if 'gcp' in text_lower or 'google cloud' in text_lower:
        found_clouds.append('Google Cloud')
    
    return found_clouds

def _extract_soft_skills_from_job(text: str) -> list:
    """Extract soft skills from job description."""
    soft_skills = ['communication', 'leadership', 'teamwork', 'problem solving', 'analytical',
                  'creative', 'adaptable', 'organized', 'detail-oriented', 'time management']
    
    found_skills = []
    text_lower = text.lower()
    
    for skill in soft_skills:
        if skill in text_lower:
            if skill == 'problem solving':
                found_skills.append('Problem Solving')
            elif skill == 'time management':
                found_skills.append('Time Management')
            elif skill == 'detail-oriented':
                found_skills.append('Detail-Oriented')
            else:
                found_skills.append(skill.title())
    
    return found_skills

def _extract_years_experience(text: str) -> str:
    """Extract years of experience requirement."""
    import re
    
    # Look for year patterns
    year_patterns = [
        r'(\d+)[-+]?\s*years?',
        r'(\d+)\s*to\s*(\d+)\s*years?',
        r'minimum\s*(\d+)\s*years?',
        r'at least\s*(\d+)\s*years?'
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, text.lower())
        if match:
            return f"{match.group(1)}+ years"
    
    return "2-3 years"

def _extract_education_requirements(text: str) -> str:
    """Extract education requirements."""
    text_lower = text.lower()
    
    if 'phd' in text_lower or 'doctorate' in text_lower:
        return 'PhD'
    elif 'master' in text_lower or 'msc' in text_lower or 'ms' in text_lower:
        return "Master's Degree"
    elif 'bachelor' in text_lower or 'bsc' in text_lower or 'bs' in text_lower or 'degree' in text_lower:
        return "Bachelor's Degree"
    
    return "Bachelor's Degree"

def _extract_skills_from_text(text: str) -> list:
    """Extract individual skills from a text snippet."""
    import re
    
    # Split by common delimiters
    skills = re.split(r'[,;•·\n\r]+', text)
    
    cleaned_skills = []
    for skill in skills:
        skill = skill.strip().strip('-•·').strip()
        if skill and len(skill) > 2 and len(skill) < 50:
            cleaned_skills.append(skill.title())
    
    return cleaned_skills[:10]  # Limit to 10

# STEP 2 HELPERS: Resume Content Analysis
def _get_empty_resume_analysis() -> dict:
    """Return empty resume analysis structure."""
    return {
        'personal_info': {
            'name': 'Your Name', 'email': '', 'phone': '', 'location': '',
            'github': '', 'linkedin': '', 'website': '', 'title': ''
        },
        'summary': '',
        'skills': {
            'programming': [], 'database': [], 'ai_ml_tools': [], 
            'tools_methodologies': [], 'soft_skills': [], 'additional': [], 'all_skills': []
        },
        'experience': [], 'education': [], 'projects': [],
        'certifications': [], 'languages': [],
        'total_experience_years': 0, 'education_level': "Bachelor's Degree"
    }

def _extract_email_from_resume(resume_text: str) -> str:
    """Extract email from resume."""
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, resume_text)
    return matches[0] if matches else ''

def _extract_phone_from_resume(resume_text: str) -> str:
    """Extract phone number from resume."""
    import re
    phone_patterns = [
        r'\+?\d{1,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    ]
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, resume_text)
        if matches:
            return matches[0]
    
    return ''

def _extract_location_from_resume(resume_text: str) -> str:
    """Extract location from resume."""
    import re
    
    # Look for city, country patterns
    location_patterns = [
        r'([A-Za-z\s]+),\s*([A-Za-z\s]+)(?:\s*,\s*([A-Za-z\s]+))?',  # City, State/Country
        r'([A-Za-z\s]+),\s*([A-Z]{2,3})\b',  # City, State Code
    ]
    
    lines = resume_text.split('\n')[:10]  # Check first 10 lines
    
    for line in lines:
        for pattern in location_patterns:
            matches = re.findall(pattern, line)
            for match in matches:
                if len(' '.join(match)) < 50:  # Reasonable length
                    return ', '.join(filter(None, match))
    
    return ''

def _extract_github_from_resume(resume_text: str) -> str:
    """Extract GitHub URL from resume."""
    import re
    github_pattern = r'https?://(?:www\\.)?github\\.com/[A-Za-z0-9_.-]+/?'
    matches = re.findall(github_pattern, resume_text)
    return matches[0] if matches else ''

def _extract_linkedin_from_resume(resume_text: str) -> str:
    """Extract LinkedIn URL from resume."""
    import re
    linkedin_pattern = r'https?://(?:www\\.)?linkedin\\.com/in/[A-Za-z0-9_.-]+/?'
    matches = re.findall(linkedin_pattern, resume_text)
    return matches[0] if matches else ''

def _extract_website_from_resume(resume_text: str) -> str:
    """Extract personal website from resume."""
    import re
    # Look for portfolio or personal website URLs
    website_patterns = [
        r'https?://(?:www\\.)?[a-zA-Z0-9-]+\\.(?:com|org|net|dev|io)/? *(?:portfolio|about|resume)?/?',
        r'\b[a-zA-Z0-9-]+\.(?:com|org|net|dev|io)\b'
    ]
    
    for pattern in website_patterns:
        matches = re.findall(pattern, resume_text)
        for match in matches:
            # Exclude common platforms
            if not any(platform in match.lower() for platform in ['github', 'linkedin', 'twitter', 'facebook']):
                return match if match.startswith('http') else f'https://{match}'
    
    return ''

def _extract_current_title_from_resume(resume_text: str) -> str:
    """Extract current job title from resume."""
    lines = resume_text.split('\n')
    
    # Look for title after name  
    for i, line in enumerate(lines[:15]):
        line = line.strip()
        if not line:
            continue
            
        # Skip name line, look for title patterns
        title_indicators = ['engineer', 'developer', 'analyst', 'manager', 'lead', 'senior', 'consultant']
        if any(indicator in line.lower() for indicator in title_indicators) and len(line) < 100:
            return line
    
    return ''

# Resume skills extraction functions
def _extract_programming_skills_from_resume(resume_text: str) -> list:
    """Extract programming skills from resume."""
    return _extract_programming_languages(resume_text)

def _extract_database_skills_from_resume(resume_text: str) -> list:
    """Extract database skills from resume."""
    return _extract_databases(resume_text)

def _extract_ai_ml_skills_from_resume(resume_text: str) -> list:
    """Extract AI/ML skills from resume."""
    ai_ml_tools = ['tensorflow', 'pytorch', 'scikit-learn', 'keras', 'pandas', 'numpy', 
                   'matplotlib', 'seaborn', 'jupyter', 'opencv', 'nltk', 'spacy']
    
    found_tools = []
    text_lower = resume_text.lower()
    
    for tool in ai_ml_tools:
        if tool in text_lower:
            if tool == 'scikit-learn':
                found_tools.append('scikit-learn')
            elif tool == 'opencv':
                found_tools.append('OpenCV')
            elif tool == 'nltk':
                found_tools.append('NLTK')
            elif tool == 'spacy':
                found_tools.append('spaCy')
            else:
                found_tools.append(tool.title())
    
    return found_tools

def _extract_tools_methodologies_from_resume(resume_text: str) -> list:
    """Extract tools and methodologies from resume."""
    tools = _extract_tools_frameworks(resume_text) + _extract_cloud_platforms(resume_text)
    
    # Add methodologies
    methodologies = ['agile', 'scrum', 'devops', 'ci/cd', 'tdd', 'bdd']
    text_lower = resume_text.lower()
    
    for method in methodologies:
        if method in text_lower:
            if method == 'ci/cd':
                tools.append('CI/CD')
            elif method == 'tdd':
                tools.append('TDD')
            elif method == 'bdd':
                tools.append('BDD')
            else:
                tools.append(method.title())
    
    return tools

def _extract_soft_skills_from_resume(resume_text: str) -> list:
    """Extract soft skills from resume."""
    return _extract_soft_skills_from_job(resume_text)

def _extract_additional_skills_from_resume(resume_text: str) -> list:
    """Extract additional skills from resume."""
    additional = []
    
    # Look for certifications
    cert_keywords = ['certified', 'certification', 'aws', 'azure', 'google cloud', 'cisco', 'microsoft']
    text_lower = resume_text.lower()
    
    for cert in cert_keywords:
        if cert in text_lower:
            additional.append(f"{cert.title()} Certified")
    
    # Look for languages
    languages = ['spanish', 'french', 'german', 'chinese', 'japanese', 'korean']
    for lang in languages:
        if lang in text_lower:
            additional.append(f"Fluent in {lang.title()}")
    
    return list(set(additional))

def _extract_experience_detailed_from_resume(resume_text: str) -> list:
    """Extract detailed experience from resume."""
    import re
    
    experiences = []
    
    # Look for experience section
    experience_section = _extract_section_content(resume_text, 'experience')
    if not experience_section:
        experience_section = resume_text  # Fallback to full text
    
    # Split into job entries (look for date patterns)
    date_pattern = r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|\d{4}\s*-\s*\d{4}|\d{1,2}/\d{4}'
    
    # Split text into potential job blocks
    job_blocks = re.split(r'\n(?=.*(?:' + date_pattern + '))', experience_section)
    
    for block in job_blocks[:5]:  # Limit to 5 most recent
        if len(block.strip()) < 20:
            continue
            
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
            
        # Extract job title, dates, and bullets
        title = lines[0] if lines else 'Software Engineer'
        dates = _extract_dates_from_text(block)
        bullets = _extract_bullets_from_text(block)
        
        if bullets:  # Only add if we found actual content
            experiences.append({
                'title': title[:50],  # Limit length
                'dates': dates or 'Recent',
                'bullets': bullets[:5]  # Max 5 bullets
            })
    
    return experiences

def _extract_education_detailed_from_resume(resume_text: str) -> list:
    """Extract detailed education from resume."""
    import re
    education = []
    
    education_section = _extract_section_content(resume_text, 'education')
    if not education_section:
        return education
    
    # Look for degree patterns
    degree_patterns = [
        r'(?i)(bachelor|master|phd|doctorate|bs|ms|ba|ma).*(?:in|of)\s*([^\n]+)',
        r'(?i)(bachelor|master|phd|doctorate)\s*([^\n]+)'
    ]
    
    lines = education_section.split('\n')
    current_entry = {}
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check for degree
        for pattern in degree_patterns:
            match = re.search(pattern, line)
            if match:
                degree = match.group(0)
                # Look for institution in same line or next lines
                institution = _extract_institution_from_line(line) or 'University'
                dates = _extract_dates_from_text(line) or 'Graduated'
                location = _extract_location_from_text(line) or ''
                
                education.append({
                    'degree': degree.title(),
                    'institution': institution,
                    'dates': dates,
                    'location': location
                })
                break
    
    return education

def _extract_projects_detailed_from_resume(resume_text: str) -> list:
    """Extract detailed projects from resume."""
    import re
    projects = []
    
    projects_section = _extract_section_content(resume_text, 'projects')
    if not projects_section:
        return projects
    
    # Split into project blocks
    project_blocks = re.split(r'\n(?=[A-Z])', projects_section)
    
    for block in project_blocks[:5]:  # Max 5 projects
        if len(block.strip()) < 20:
            continue
            
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
            
        title = lines[0] if lines else 'Personal Project'
        dates = _extract_dates_from_text(block) or 'Recent'
        bullets = _extract_bullets_from_text(block)
        
        if bullets:
            projects.append({
                'title': title[:50],
                'dates': dates,
                'bullets': bullets[:4]  # Max 4 bullets
            })
    
    return projects

def _extract_summary_from_resume(resume_text: str) -> str:
    """Extract professional summary from resume."""
    # Look for summary section
    summary_section = _extract_section_content(resume_text, 'summary')
    if summary_section:
        # Take first paragraph
        paragraphs = summary_section.split('\n\n')
        return paragraphs[0].strip()[:500]  # Max 500 chars
    
    return ''

def _extract_certifications_from_resume(resume_text: str) -> list:
    """Extract certifications from resume."""
    certs = []
    
    cert_section = _extract_section_content(resume_text, 'certification')
    text_to_search = cert_section or resume_text
    
    # Common certification patterns
    cert_patterns = ['aws', 'azure', 'google cloud', 'cisco', 'microsoft', 'oracle', 'pmp']
    
    for cert in cert_patterns:
        if cert in text_to_search.lower():
            certs.append(f"{cert.title()} Certified")
    
    return certs

def _extract_languages_from_resume(resume_text: str) -> list:
    """Extract languages from resume."""
    languages = []
    
    # Look for language indicators
    lang_keywords = ['spanish', 'french', 'german', 'chinese', 'japanese', 'korean', 'portuguese']
    
    for lang in lang_keywords:
        if lang in resume_text.lower():
            languages.append(lang.title())
    
    return languages

def _calculate_total_experience_years(experience: list) -> int:
    """Calculate total years of experience."""
    # Simple heuristic: number of jobs * average 2 years per job
    return len(experience) * 2

def _determine_education_level(education: list) -> str:
    """Determine highest education level."""
    if not education:
        return "Bachelor's Degree"
    
    for edu in education:
        degree = edu.get('degree', '').lower()
        if 'phd' in degree or 'doctorate' in degree:
            return 'PhD'
        elif 'master' in degree or 'ms' in degree or 'ma' in degree:
            return "Master's Degree"
    
    return "Bachelor's Degree"

# STEP 3 HELPERS: Comparison Analysis
def _compare_experience_levels(resume_years: int, required_years: str) -> float:
    """Compare experience levels and return match score."""
    if not required_years or 'years' not in required_years.lower():
        return 75.0  # Default moderate match
    
    import re
    numbers = re.findall(r'\d+', required_years)
    if numbers:
        required = int(numbers[0])
        if resume_years >= required:
            return 100.0
        elif resume_years >= required * 0.8:
            return 80.0
        elif resume_years >= required * 0.6:
            return 60.0
        else:
            return 40.0
    
    return 75.0

def _compare_education_levels(resume_education: str, required_education: str) -> float:
    """Compare education levels and return match score."""
    education_hierarchy = {
        'phd': 4,
        'doctorate': 4,
        "master's degree": 3,
        "bachelor's degree": 2,
        'associate degree': 1,
        'high school': 0
    }
    
    resume_level = education_hierarchy.get(resume_education.lower(), 2)
    required_level = education_hierarchy.get(required_education.lower(), 2)
    
    if resume_level >= required_level:
        return 100.0
    elif resume_level >= required_level - 1:
        return 75.0
    else:
        return 50.0

def _generate_tailoring_recommendations(resume_analysis: dict, job_analysis: dict, 
                                      matched_skills: list, missing_skills: list) -> list:
    """Generate specific tailoring recommendations."""
    recommendations = []
    
    # Skills recommendations
    if missing_skills:
        recommendations.append(f"Add these key skills to your resume: {', '.join(missing_skills[:5])}")
    
    # Experience recommendations
    if job_analysis['years_required'] and resume_analysis['total_experience_years'] < 3:
        recommendations.append("Highlight any relevant internships, projects, or part-time experience to show more depth")
    
    # Summary recommendations
    if not resume_analysis['summary']:
        recommendations.append("Add a professional summary tailored to this role")
    
    # Projects recommendations
    if len(resume_analysis['projects']) < 2:
        recommendations.append("Add more relevant projects that showcase your technical skills")
    
    return recommendations

def _generate_ats_optimization_suggestions(resume_analysis: dict, job_analysis: dict, 
                                         missing_skills: list) -> list:
    """Generate ATS optimization suggestions."""
    suggestions = []
    
    if missing_skills:
        suggestions.append(f"Integrate these keywords: {', '.join(missing_skills[:3])}")
    
    suggestions.append("Use exact job title from posting in your professional title")
    suggestions.append("Include relevant keywords in your experience bullet points")
    
    return suggestions

def _identify_priority_improvements(missing_skills: list, job_analysis: dict) -> list:
    """Identify priority improvements based on must-have skills."""
    priority = []
    
    must_haves = job_analysis.get('must_have_skills', [])
    for skill in missing_skills:
        if skill in must_haves:
            priority.append(f"Critical: Add experience with {skill}")
    
    return priority[:3]

# STEP 4 HELPERS: Resume Optimization
def _optimize_personal_info(personal_info: dict, target_job_title: str) -> dict:
    """Optimize personal information."""
    optimized = personal_info.copy()
    
    # Set professional title
    if target_job_title:
        optimized['title'] = target_job_title
    
    return optimized

def _generate_tailored_summary(resume_analysis: dict, job_analysis: dict, target_job_title: str) -> str:
    """Generate tailored professional summary."""
    
    # Get key elements
    experience_years = resume_analysis['total_experience_years']
    top_skills = job_analysis['must_have_skills'][:3]
    company_needs = job_analysis['soft_skills'][:2]
    
    # Build tailored summary
    summary_parts = []
    
    if experience_years > 0:
        summary_parts.append(f"{experience_years}+ years of experience in software development")
    else:
        summary_parts.append("Passionate software developer")
    
    if top_skills:
        summary_parts.append(f"with expertise in {', '.join(top_skills)}")
    
    if company_needs:
        summary_parts.append(f"Strong {' and '.join(company_needs).lower()} skills")
    
    summary_parts.append(f"Seeking to contribute to a dynamic team as a {target_job_title}")
    
    return '. '.join(summary_parts) + '.'

def _optimize_skills_for_ats(skills: dict, job_analysis: dict, missing_skills: list) -> dict:
    """Optimize skills organization for ATS."""
    optimized = skills.copy()
    
    # Add missing critical skills (with a note that these should be validated)
    for skill in missing_skills[:3]:  # Add top 3 missing skills
        if any(prog in skill.lower() for prog in ['python', 'java', 'javascript']):
            if skill not in optimized['programming']:
                optimized['programming'].append(skill)
        elif any(db in skill.lower() for db in ['sql', 'mysql', 'postgres']):
            if skill not in optimized['database']:
                optimized['database'].append(skill)
        else:
            if skill not in optimized['tools_methodologies']:
                optimized['tools_methodologies'].append(skill)
    
    return optimized

def _optimize_experience_descriptions(experience: list, job_analysis: dict, missing_skills: list) -> list:
    """Optimize experience descriptions with job-relevant keywords."""
    optimized = []
    
    for exp in experience:
        optimized_exp = exp.copy()
        
        # Enhance bullets with relevant keywords
        enhanced_bullets = []
        for bullet in exp['bullets']:
            enhanced_bullet = bullet
            
            # Add relevant keywords naturally (simplified)
            for skill in missing_skills[:2]:
                if skill.lower() not in bullet.lower() and len(enhanced_bullet) < 150:
                    enhanced_bullet = bullet  # Keep original for now
            
            enhanced_bullets.append(enhanced_bullet)
        
        optimized_exp['bullets'] = enhanced_bullets
        optimized.append(optimized_exp)
    
    return optimized

def _optimize_education_for_job(education: list, job_analysis: dict) -> list:
    """Optimize education formatting for job."""
    return education  # Keep as-is for now

def _optimize_projects_for_job(projects: list, job_analysis: dict, missing_skills: list) -> list:
    """Optimize projects with job-relevant context."""
    return projects  # Keep as-is for now

def _calculate_ats_score(job_analysis: dict, optimized_skills: dict) -> int:
    """Calculate estimated ATS score."""
    # Simple heuristic based on keyword matches
    job_keywords = job_analysis.get('all_keywords', [])
    resume_skills = (optimized_skills['programming'] + optimized_skills['database'] + 
                    optimized_skills['tools_methodologies'])
    
    matches = len(set(skill.lower() for skill in resume_skills) & 
                 set(skill.lower() for skill in job_keywords))
    
    if not job_keywords:
        return 75
    
    score = (matches / len(job_keywords)) * 100
    return min(95, max(60, int(score)))  # Between 60-95

# Utility helper functions
def _extract_section_content(text: str, section_name: str) -> str:
    """Extract content from a specific resume section."""
    import re
    
    # Look for section headers
    pattern = rf'(?i)\b{section_name}\b.*?(?=\n[A-Z][A-Z\s]+:|\n\n[A-Z]|$)'
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        return match.group(0)
    
    return ''

def _extract_dates_from_text(text: str) -> str:
    """Extract date ranges from text."""
    import re
    
    date_patterns = [
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s*-\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}|Present',
        r'\d{4}\s*-\s*\d{4}',
        r'\d{1,2}/\d{4}\s*-\s*\d{1,2}/\d{4}'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    return ''

def _extract_bullets_from_text(text: str) -> list:
    """Extract bullet points from text."""
    import re
    
    # Look for bullet patterns
    bullet_patterns = [
        r'^\s*[•·\-\*]\s+(.+)$',
        r'^\s*\d+\.\s+(.+)$',
        r'^\s*[A-Z][^\n]{20,200}$'  # Sentences that look like bullets
    ]
    
    bullets = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 20:
            continue
            
        for pattern in bullet_patterns:
            match = re.match(pattern, line, re.MULTILINE)
            if match:
                bullets.append(match.group(1) if match.lastindex else line)
                break
    
    return bullets[:8]  # Max 8 bullets

def _extract_institution_from_line(line: str) -> str:
    """Extract institution name from education line."""
    # Look for common university keywords
    uni_keywords = ['university', 'college', 'institute', 'school']
    
    for keyword in uni_keywords:
        if keyword in line.lower():
            # Try to extract institution name
            parts = line.split(',')
            for part in parts:
                if keyword in part.lower():
                    return part.strip()
    
    return ''

def _extract_location_from_text(text: str) -> str:
    """Extract location from a text line."""
    import re
    
    # Look for city, state patterns
    location_pattern = r'([A-Za-z\s]+),\s*([A-Z]{2}|[A-Za-z\s]+)$'
    match = re.search(location_pattern, text)
    
    if match:
        return match.group(0)
    
    return ''