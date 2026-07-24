from django.urls import path, include
from . import views
from . import coach_views
from . import career_views, resume_views, security_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
   
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', 
        views.CustomPasswordResetConfirmView.as_view(), 
        name='password_reset_confirm'),
    path('password-reset/complete/', 
        views.CustomPasswordResetCompleteView.as_view(), 
        name='password_reset_complete'),
    path('register/', views.register, name='register'),
    path('social-auth/', include('social_django.urls', namespace='social')),

    path('ai_job_info/', views.ai_job_info, name='ai_job_info'),

    path('cv-analysis/', career_views.cv_import, name='cv_analysis'),
    # Removed deprecated cv-analysis-process endpoint

    # Removed AI resume builder routes
    path('customer-support/', views.customer_support, name='customer_support'),
    # Old delete endpoints removed with AI-driven flow

    path('interview-prep/', views.topic_list, name='interview_prep'),
    path('topic/<slug:topic_slug>/', views.question_list, name='question_list'),
    path('question/<int:question_id>/', views.coding_assessment, name='coding_assessment'),
    path('question/<int:question_id>/run/', security_views.coding_execution_disabled, name='run_code'),
    path('question/<int:question_id>/save_code', views.save_code, name='save_code'),
    path('question/<int:question_id>/get_saved_code', views.get_saved_code, name='get_saved_code'),

    path('your-profile/', views.your_profile, name='your_profile'),
    # Job search removed: it relied on in-process headless Chrome, which cannot
    # run on a serverless runtime with a read-only filesystem.
    path('upload/', views.file_upload, name='file_upload'),

    # Personal AI Interview Coach and Career Memory
    path('coach/', coach_views.coach_dashboard, name='coach_dashboard'),
    path('coach/profile/', coach_views.coach_profile_update, name='coach_profile_update'),
    path('coach/skills/add/', coach_views.coach_skill_add, name='coach_skill_add'),
    path('coach/skills/<int:skill_id>/delete/', coach_views.coach_skill_delete, name='coach_skill_delete'),
    path('coach/memory/<int:fact_id>/confirm/', coach_views.coach_memory_confirm, name='coach_memory_confirm'),
    path('coach/memory/<int:fact_id>/edit/', coach_views.coach_memory_edit, name='coach_memory_edit'),
    path('coach/memory/<int:fact_id>/reject/', coach_views.coach_memory_reject, name='coach_memory_reject'),
    path('coach/memory/<int:fact_id>/delete/', coach_views.coach_memory_delete, name='coach_memory_delete'),
    path('coach/start/', coach_views.coach_start, name='coach_start'),
    path('coach/session/<int:session_id>/', coach_views.coach_session, name='coach_session'),
    path('coach/session/<int:session_id>/answer/', coach_views.coach_answer, name='coach_answer'),
    path('coach/session/<int:session_id>/finish/', coach_views.coach_finish, name='coach_finish'),
    path('coach/session/<int:session_id>/delete/', coach_views.coach_session_delete, name='coach_session_delete'),
    path('coach/cv-import/', career_views.cv_import, name='cv_import'),
    path('coach/uploads/<int:document_id>/delete/', career_views.candidate_document_delete, name='candidate_document_delete'),
    path('privacy/', career_views.privacy_center, name='privacy_center'),
    path('privacy/export/', career_views.data_export, name='data_export'),
    path('privacy/delete-account/', career_views.account_delete, name='account_delete'),
    
    # Truthful, persisted resume builder (legacy session-only routes retired).
    path('ai-resume/', resume_views.resume_builder, name='ai_resume_upload'),
    path('resumes/', resume_views.resume_builder, name='resume_builder'),
    path('resumes/<int:version_id>/', resume_views.resume_editor, name='resume_editor'),
    path('resumes/<int:version_id>/save/', resume_views.resume_save, name='resume_save'),
    path('resumes/<int:version_id>/export/pdf/', resume_views.resume_export_pdf, name='resume_export_pdf'),
    path('resumes/<int:version_id>/export/docx/', resume_views.resume_export_docx, name='resume_export_docx'),
    path('resumes/<int:version_id>/delete/', resume_views.resume_delete, name='resume_delete'),
    
]
