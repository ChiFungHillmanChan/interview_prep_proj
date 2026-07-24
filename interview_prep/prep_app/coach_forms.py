from django import forms

from .models import CareerMemoryFact, CareerProfile, InterviewSession, SkillEvidence


FIELD_CLASS = (
    'mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 '
    'text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100'
)


class CareerProfileForm(forms.ModelForm):
    class Meta:
        model = CareerProfile
        fields = [
            'target_role',
            'goals',
            'preferred_language',
            'interview_style',
            'desired_difficulty',
        ]
        widgets = {
            'target_role': forms.TextInput(attrs={
                'class': FIELD_CLASS,
                'placeholder': 'e.g. Junior Django Developer',
            }),
            'goals': forms.Textarea(attrs={
                'class': FIELD_CLASS,
                'rows': 3,
                'placeholder': 'What do you want the coach to help you improve?',
            }),
            'preferred_language': forms.Select(attrs={'class': FIELD_CLASS}),
            'interview_style': forms.Select(attrs={'class': FIELD_CLASS}),
            'desired_difficulty': forms.Select(attrs={'class': FIELD_CLASS}),
        }


class SkillEvidenceForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'e.g. Django, stakeholder communication',
        }),
    )
    self_level = forms.ChoiceField(
        choices=SkillEvidence.LEVEL_CHOICES,
        widget=forms.Select(attrs={'class': FIELD_CLASS}),
    )
    evidence = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': FIELD_CLASS,
            'rows': 2,
            'placeholder': 'Where have you used this skill? A project or result is best.',
        }),
    )

    def clean_name(self):
        return ' '.join(self.cleaned_data['name'].split())


class StartInterviewForm(forms.Form):
    target_role = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'e.g. Graduate Software Engineer',
        }),
    )
    job_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': FIELD_CLASS,
            'rows': 7,
            'placeholder': 'Paste the job description for a highly tailored interview (optional).',
        }),
    )
    focus_areas = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': FIELD_CLASS,
            'placeholder': 'e.g. Django, system design, confidence',
        }),
        help_text='Separate multiple areas with commas.',
    )
    category = forms.ChoiceField(
        choices=InterviewSession.CATEGORY_CHOICES,
        initial='mixed',
        required=False,
        widget=forms.Select(attrs={'class': FIELD_CLASS}),
    )
    language = forms.ChoiceField(
        choices=CareerProfile.LANGUAGE_CHOICES,
        initial='english',
        required=False,
        widget=forms.Select(attrs={'class': FIELD_CLASS}),
    )

    def clean_focus_areas(self):
        raw = self.cleaned_data.get('focus_areas', '')
        return list(dict.fromkeys(part.strip() for part in raw.split(',') if part.strip()))[:8]

    def clean_category(self):
        return self.cleaned_data.get('category') or 'mixed'

    def clean_language(self):
        return self.cleaned_data.get('language') or 'english'


class InterviewAnswerForm(forms.Form):
    answer = forms.CharField(
        min_length=10,
        # Generous for a spoken-style answer (~1300 words). Without a ceiling
        # the whole body went into the model prompt verbatim and was stored in
        # full, then re-embedded in every later prompt in the same session.
        max_length=8000,
        widget=forms.Textarea(attrs={
            'class': FIELD_CLASS,
            'rows': 9,
            'placeholder': 'Answer naturally. Use a real example when you can—honest evidence gives a better assessment.',
            'autofocus': True,
        }),
    )


class CVUploadForm(forms.Form):
    cv_file = forms.FileField(
        help_text='PDF or DOCX, up to 10 MB. The uploaded binary is parsed and discarded.',
        widget=forms.ClearableFileInput(attrs={
            'class': FIELD_CLASS,
            'accept': '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
    )


class CareerMemoryEditForm(forms.ModelForm):
    class Meta:
        model = CareerMemoryFact
        fields = ['title', 'content', 'evidence']
        widgets = {
            'title': forms.TextInput(attrs={'class': FIELD_CLASS}),
            'content': forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 4}),
            'evidence': forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 3}),
        }

    def clean_evidence(self):
        evidence = self.cleaned_data['evidence'].strip()
        if not evidence:
            raise forms.ValidationError('Every Career Memory item needs an evidence excerpt.')
        return evidence


class ResumeBuilderForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        initial='Tailored resume',
        widget=forms.TextInput(attrs={'class': FIELD_CLASS}),
    )
    target_role = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': FIELD_CLASS, 'placeholder': 'e.g. Backend Engineer'}),
    )
    job_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': FIELD_CLASS, 'rows': 8, 'placeholder': 'Paste the target job description'}),
    )


class SessionDeleteForm(forms.Form):
    delete_generated_memory = forms.BooleanField(required=False)


class AccountDeleteForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': FIELD_CLASS}))
