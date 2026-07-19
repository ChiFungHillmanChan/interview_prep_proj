from django import forms
from .models import UserSubmission
from django.contrib.auth.forms import AuthenticationForm , UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import os

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'Enter your email'
        })
    )
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'Choose a username'
        })
    )
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'Enter password'
        })
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class AIResumeUploadForm(forms.Form):
    """Form for AI Resume Builder Page 1 - Upload"""
    
    job_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., Software Engineer at Google'
        }),
        help_text='Short descriptive name for this job application'
    )
    
    job_title = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., Senior Software Engineer'
        }),
        help_text='The exact job title from the posting'
    )
    
    job_description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 8,
            'placeholder': 'Paste the complete job posting including requirements, responsibilities, and qualifications...'
        }),
        required=True,
        help_text='Paste the complete job posting including requirements, responsibilities, and qualifications'
    )
    
    resume_file = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'file-input',
            'accept': '.pdf,.docx'
        }),
        help_text='PDF or DOCX files only (max 10MB)'
    )
    
    extra_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 4,
            'placeholder': 'Additional information about your experience, achievements, or specific requirements not in your resume...'
        }),
        required=False,
        help_text='Additional information about your experience, achievements, or specific requirements not in your resume'
    )
    
    def clean_job_description(self):
        job_description = self.cleaned_data.get('job_description', '').strip()
        
        if len(job_description) < 50:
            raise ValidationError('Job description seems too short. Please provide more details about the role.')
        
        if len(job_description) > 10000:
            raise ValidationError('Job description is too long. Please limit to 10,000 characters.')
        
        return job_description
    
    def clean_job_name(self):
        job_name = self.cleaned_data.get('job_name', '').strip()
        
        if len(job_name) < 3:
            raise ValidationError('Job name is too short.')
        
        return job_name
    
    def clean_job_title(self):
        job_title = self.cleaned_data.get('job_title', '').strip()
        
        if len(job_title) < 3:
            raise ValidationError('Job title seems too short.')
        
        return job_title
    
    def clean_resume_file(self):
        resume_file = self.cleaned_data.get('resume_file')
        
        if not resume_file:
            raise ValidationError('Please upload your resume file.')
        
        # Check file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB in bytes
        if resume_file.size > max_size:
            max_mb = max_size / (1024 * 1024)
            raise ValidationError(f'File size ({self._format_file_size(resume_file.size)}) exceeds {max_mb}MB limit.')
        
        # Check file extension
        file_name = resume_file.name.lower()
        allowed_extensions = ['.pdf', '.docx']
        
        if not any(file_name.endswith(ext) for ext in allowed_extensions):
            raise ValidationError(
                f'Invalid file type. Only PDF and DOCX files are allowed. '
                f'You uploaded: {resume_file.name}'
            )
        
        # Check MIME type if available
        allowed_mime_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        
        if hasattr(resume_file, 'content_type') and resume_file.content_type:
            if resume_file.content_type not in allowed_mime_types:
                raise ValidationError(
                    f'Invalid file format detected. Only PDF and DOCX files are supported. '
                    f'Detected type: {resume_file.content_type}'
                )
        
        # Check for empty files
        if resume_file.size == 0:
            raise ValidationError('The uploaded file is empty or corrupted.')
        
        return resume_file
    
    def clean_extra_notes(self):
        extra_notes = self.cleaned_data.get('extra_notes', '').strip()
        
        if len(extra_notes) > 5000:
            raise ValidationError('Extra notes are too long. Please limit to 5,000 characters.')
        
        return extra_notes
    
    def _format_file_size(self, bytes_size):
        """Format file size in human readable format"""
        if bytes_size == 0:
            return '0 Bytes'
        
        k = 1024
        sizes = ['Bytes', 'KB', 'MB', 'GB']
        i = int(bytes_size.bit_length() - 1) // 10
        i = min(i, len(sizes) - 1)
        
        return f'{bytes_size / (k ** i):.2f} {sizes[i]}'
    
class JobInfoForm(forms.Form):
    job_role = forms.CharField(max_length=100)
    company_name = forms.CharField(max_length=100)
    job_description = forms.CharField(widget=forms.Textarea)

class UserProfileForm(forms.Form):
    OPPORTUNITY_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('graduate_scheme', 'Graduate Scheme'),
        ('graduate_job', 'Graduate Job'),
        ('postgraduate_study', 'Postgraduate Study'),
        ('placement', 'Placement'),
    ]

    SECTOR_CHOICES = [
       ('accounting_finance', 'Accounting & Finance'),
        ('agriculture_animals_plants', 'Agriculture, Animals & Plants'),
        ('banking_insurance_financial_services', 'Banking, Insurance & Financial Services'),
        ('charity_public_civil_service', 'Charity, Public & Civil Service'),
        ('consulting', 'Consulting'),
        ('creative_arts_design', 'Creative Arts & Design'),
        ('engineering', 'Engineering'),
        ('hospitality_sport_leisure_tourism', 'Hospitality, Sport, Leisure & Tourism'),
        ('hr_recruitment', 'HR & Recruitment'),
        ('investment_banking_fund_management', 'Investment Banking & Fund Management'),
        ('languages_libraries_culture', 'Languages, Libraries & Culture'),
        ('law', 'Law'),
        ('management_business', 'Management & Business'),
        ('marketing_advertising_pr', 'Marketing, Advertising & PR'),
        ('media_journalism_publishing', 'Media, Journalism & Publishing'),
        ('medical_healthcare_dental', 'Medical, Healthcare & Dental'),
        ('procurement_supply_chain', 'Procurement & Supply Chain'),
        ('property_construction_qs', 'Property, Construction & QS'),
        ('retail_business_commercial_services', 'Retail, Business & Commercial Services'),
        ('science_rd_food_industry', 'Science, R&D, Food Industry'),
        ('teaching_education', 'Teaching & Education'),
        ('technology', 'Technology'),

    ]

    opportunity_types = forms.MultipleChoiceField(
        choices=OPPORTUNITY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    sectors = forms.MultipleChoiceField(
        choices=SECTOR_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    preferred_locations = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Enter preferred office locations, one per line."
    )
    education = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text="Enter your educational background."
    )
    diversity = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text="Optional: Share any diversity information you'd like us to know."
    )
    skills = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        help_text="List your key skills, separated by commas."
    )
    languages = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="List languages you speak, with proficiency levels."
    )
    cv = forms.FileField(
        label="Upload your CV",
        help_text="Accepted formats: PDF, DOC, DOCX"
    )

class CVAnalysisForm(forms.Form):
    job_role = forms.CharField(max_length=100)
    company_name = forms.CharField(max_length=100)
    job_description = forms.CharField(widget=forms.Textarea)
    cv_file = forms.FileField()



class CustomAuthenticationForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            }
        )
    )
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your username'
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'appearance-none block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter your password'
            }
        )
    )


class CodeSubmissionForm(forms.ModelForm):
    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('java', 'Java'),
        ('javascript', 'JavaScript'),
        ('cpp', 'C++'),
    ]

    code = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'w-full h-96 font-mono bg-gray-900 text-gray-100 p-4 rounded-lg',
                'spellcheck': 'false',
            }
        )
    )
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        widget=forms.Select(
            attrs={
                'class': 'bg-gray-800 text-gray-100 rounded-lg p-2'
            }
        )
    )

    class Meta:
        model = UserSubmission
        fields = ['code', 'language']


class ResumeUploadForm(forms.Form):
    """Form for initial resume upload"""
    resume_file = forms.FileField(
        label="Upload your resume",
        help_text="Supported formats: PDF, DOCX, TXT",
        widget=forms.FileInput(attrs={
            'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
            'accept': '.pdf,.docx,.doc,.txt'
        })
    )


class JobDescriptionForm(forms.Form):
    """Form for job description input"""
    job_role = forms.CharField(
        max_length=200,
        label="Job Title",
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'e.g., Software Engineer, Product Manager'
        })
    )
    company_name = forms.CharField(
        max_length=200,
        label="Company Name",
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'placeholder': 'e.g., Google, Microsoft'
        })
    )
    job_description = forms.CharField(
        label="Job Description",
        widget=forms.Textarea(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            'rows': 10,
            'placeholder': 'Paste the complete job description here...'
        }),
        help_text="Paste the full job description for best results"
    )


class TargetedQuestionsForm(forms.Form):
    """Dynamic form for targeted questions - fields added dynamically"""
    pass