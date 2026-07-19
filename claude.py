# models.py
from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    EXPERIENCE_CHOICES = [
        ('entry', 'Entry Level (0-2 years)'),
        ('mid', 'Mid Level (3-5 years)'),
        ('senior', 'Senior Level (6+ years)')
    ]
    
    AVAILABILITY_CHOICES = [
        ('0-5', '0-5 hours'),
        ('5-10', '5-10 hours'),
        ('10+', '10+ hours')
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    job_role = models.CharField(max_length=100)
    experience_level = models.CharField(max_length=10, choices=EXPERIENCE_CHOICES)
    preferred_language = models.CharField(max_length=50)
    key_skills = models.TextField()
    learning_goals = models.TextField()
    weekly_availability = models.CharField(max_length=10, choices=AVAILABILITY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CodingQuestion(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard')
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    test_cases = models.JSONField()
    solution = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(CodingQuestion, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)
    solution_submitted = models.TextField(null=True, blank=True)
    completed_at = models.DateTimeField(auto_now=True)

# forms.py
from django import forms
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        exclude = ['user', 'created_at', 'updated_at']
        widgets = {
            'key_skills': forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'}),
            'learning_goals': forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'}),
        }

# views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserProfile, CodingQuestion, UserProgress
from .forms import UserProfileForm

@login_required
def profile_setup(request):
    try:
        profile = request.user.userprofile
        form = UserProfileForm(instance=profile)
    except UserProfile.DoesNotExist:
        form = UserProfileForm()
    
    if request.method == 'POST':
        if hasattr(request.user, 'userprofile'):
            form = UserProfileForm(request.POST, instance=request.user.userprofile)
        else:
            form = UserProfileForm(request.POST)
        
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('dashboard')
    
    return render(request, 'prep_app/profile_setup.html', {'form': form})

@login_required
def dashboard(request):
    if not hasattr(request.user, 'userprofile'):
        return redirect('profile_setup')
    
    # Get suggested topics based on user profile
    profile = request.user.userprofile
    
    # Get daily challenge
    daily_challenge = CodingQuestion.objects.filter(
        difficulty='medium'
    ).order_by('?').first()
    
    # Get progress statistics
    total_questions = CodingQuestion.objects.count()
    completed_questions = UserProgress.objects.filter(
        user=request.user,
        completed=True
    ).count()
    
    completion_rate = (completed_questions / total_questions * 100) if total_questions > 0 else 0
    
    context = {
        'profile': profile,
        'daily_challenge': daily_challenge,
        'completion_rate': round(completion_rate, 1),
        'completed_questions': completed_questions,
        'total_questions': total_questions,
    }
    
    return render(request, 'prep_app/dashboard.html', context)

@login_required
def practice(request, question_id=None):
    if question_id:
        question = CodingQuestion.objects.get(pk=question_id)
    else:
        question = CodingQuestion.objects.order_by('?').first()
    
    if request.method == 'POST':
        solution = request.POST.get('solution')
        # Here you would typically:
        # 1. Run the code against test cases
        # 2. Store the results
        # 3. Update user progress
        
        UserProgress.objects.create(
            user=request.user,
            question=question,
            solution_submitted=solution,
            completed=True  # You would set this based on test results
        )
        
        messages.success(request, 'Solution submitted successfully!')
        return redirect('practice')
    
    context = {
        'question': question,
    }
    
    return render(request, 'prep_app/practice.html', context)

# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('profile/setup/', views.profile_setup, name='profile_setup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('practice/', views.practice, name='practice'),
    path('practice/<int:question_id>/', views.practice, name='practice_question'),
]