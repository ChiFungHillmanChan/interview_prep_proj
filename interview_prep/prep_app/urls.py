from django.urls import path, include
from . import views
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
    path('user-profile/', views.user_profile, name='user_profile'),

    path('cv-analysis/', views.cv_analysis, name='cv_analysis'),
    # Removed deprecated cv-analysis-process endpoint

    # Removed AI resume builder routes
    path('customer-support/', views.customer_support, name='customer_support'),
    # Old delete endpoints removed with AI-driven flow

    path('interview-prep/', views.topic_list, name='interview_prep'),
    path('topic/<slug:topic_slug>/', views.question_list, name='question_list'),
    path('question/<int:question_id>/', views.coding_assessment, name='coding_assessment'),
    path('question/<int:question_id>/run/', views.run_code, name='run_code'),
    path('question/<int:question_id>/save_code', views.save_code, name='save_code'),
    path('question/<int:question_id>/get_saved_code', views.get_saved_code, name='get_saved_code'),

    path('your-profile/', views.your_profile, name='your_profile'),
    path('job-search/', views.job_search, name='job_search'),
    path('upload/', views.file_upload, name='file_upload'),
    
    # AI Resume Builder URLs
    path('ai-resume/', views.ai_resume_upload, name='ai_resume_upload'),
    path('ai-resume/editor/', views.ai_resume_editor, name='ai_resume_editor'),
    path('ai-resume/download/', views.ai_resume_download, name='ai_resume_download'),
    path('ai-resume/export/pdf/', views.ai_resume_export_pdf, name='ai_resume_export_pdf'),
    path('ai-resume/export/docx/', views.ai_resume_export_docx, name='ai_resume_export_docx'),
    path('ai-resume/refine/', views.ai_resume_refine, name='ai_resume_refine'),
    path('ai-resume/save/', views.ai_resume_save, name='ai_resume_save'),
    path('ai-resume/clear/', views.ai_resume_clear_session, name='ai_resume_clear_session'),
    
]