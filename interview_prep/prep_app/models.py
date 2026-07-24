from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Topic(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=200, help_text="Icon class name or SVG path")
    slug = models.SlugField(unique=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['order', 'name']

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    LANGUAGE_CHOICES = [
        ('python', 'Python'),
        ('java', 'Java'),
        ('javascript', 'JavaScript'),
        ('cpp', 'C++'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='questions')
    leetcode_link = models.URLField()
    
    initial_code = models.JSONField(help_text="Initial code template for each language")
    solution = models.JSONField(help_text="Solution code for each language", null=True, blank=True)
    test_cases = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
class UserSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    code = models.TextField()
    language = models.CharField(max_length=50)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    execution_time = models.FloatField(null=True)
    memory_usage = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class UserCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey('Question', on_delete=models.CASCADE)  # Assuming you have a Question model
    language = models.CharField(max_length=20)  # To store the selected language
    code = models.TextField()
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'question', 'language']


class CareerProfile(models.Model):
    LANGUAGE_CHOICES = [
        ('english', 'English'),
        ('cantonese', 'Cantonese'),
        ('bilingual', 'English + Cantonese'),
        ('english_cantonese_feedback', 'English interview + Cantonese feedback'),
    ]
    STYLE_CHOICES = [
        ('supportive', 'Supportive'),
        ('balanced', 'Balanced'),
        ('challenging', 'Challenging'),
    ]
    DIFFICULTY_CHOICES = [
        ('adaptive', 'Adaptive'),
        ('junior', 'Junior'),
        ('mid', 'Mid-level'),
        ('senior', 'Senior'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='career_profile')
    target_role = models.CharField(max_length=200, blank=True)
    goals = models.TextField(blank=True)
    preferred_language = models.CharField(max_length=40, choices=LANGUAGE_CHOICES, default='english')
    interview_style = models.CharField(max_length=20, choices=STYLE_CHOICES, default='balanced')
    desired_difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='adaptive')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Career profile for {self.user.username}"


class SkillEvidence(models.Model):
    LEVEL_CHOICES = [
        ('unknown', 'Not sure yet'),
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    ASSESSMENT_CHOICES = [
        ('not_assessed', 'Not assessed'),
        ('developing', 'Developing'),
        ('working', 'Working knowledge'),
        ('strong', 'Strong evidence'),
    ]
    CONFIDENCE_CHOICES = [
        ('unassessed', 'Not assessed'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skill_evidence')
    name = models.CharField(max_length=100)
    self_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='unknown')
    evidence = models.TextField(blank=True)
    assessment_level = models.CharField(
        max_length=20,
        choices=ASSESSMENT_CHOICES,
        default='not_assessed',
    )
    assessment_confidence = models.CharField(
        max_length=20,
        choices=CONFIDENCE_CHOICES,
        default='unassessed',
    )
    answers_count = models.PositiveIntegerField(default=0)
    average_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_skill_per_user'),
        ]

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class InterviewSession(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
    ]
    READINESS_CHOICES = [
        ('insufficient_evidence', 'Not enough evidence yet'),
        ('building', 'Building towards the role'),
        ('mostly_ready', 'Mostly ready'),
        ('ready', 'Ready to interview'),
    ]
    CATEGORY_CHOICES = [
        ('behavioural', 'Behavioural'),
        ('technical', 'Technical discussion'),
        ('coding', 'Coding discussion'),
        ('system_design', 'System design'),
        ('graduate', 'Graduate'),
        ('leadership', 'Leadership'),
        ('product', 'Product'),
        ('data', 'Data'),
        ('mixed', 'Mixed / adaptive'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interview_sessions')
    target_role = models.CharField(max_length=200)
    job_description = models.TextField(blank=True)
    focus_areas = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='mixed')
    language = models.CharField(
        max_length=40,
        choices=CareerProfile.LANGUAGE_CHOICES,
        default='english',
    )
    plan_sections = models.JSONField(default=list, blank=True)
    current_section = models.CharField(max_length=40, default='introduction')
    current_section_index = models.PositiveSmallIntegerField(default=0)
    current_question = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    readiness_label = models.CharField(
        max_length=30,
        choices=READINESS_CHOICES,
        default='insufficient_evidence',
    )
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.target_role} interview for {self.user.username}"


class InterviewTurn(models.Model):
    CONFIDENCE_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='turns')
    section = models.CharField(max_length=40, default='introduction')
    question = models.TextField()
    answer = models.TextField()
    feedback = models.TextField()
    scores = models.JSONField(default=dict, blank=True)
    assessment_confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, default='low')
    demonstrated_skills = models.JSONField(default=list, blank=True)
    next_focus = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Turn {self.pk} in session {self.session_id}"


class CareerMemoryFact(models.Model):
    CATEGORY_CHOICES = [
        ('personal', 'Personal detail'),
        ('skill', 'Skill'),
        ('work_experience', 'Work experience'),
        ('project', 'Project'),
        ('education', 'Education'),
        ('achievement', 'Achievement'),
        ('certification', 'Certification'),
        ('language', 'Language'),
        ('experience', 'Other experience'),
        ('strength', 'Strength'),
        ('growth', 'Growth area'),
        ('preference', 'Preference'),
        ('goal', 'Goal'),
    ]
    CONFIDENCE_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    SOURCE_CHOICES = [
        ('manual', 'Added by user'),
        ('cv', 'CV import'),
        ('interview', 'Interview answer'),
    ]
    REVIEW_CHOICES = [
        ('pending', 'Needs review'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='career_memory')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=250, blank=True)
    content = models.TextField()
    evidence = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, default='low')
    user_confirmed = models.BooleanField(default=False)
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default='pending')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='manual')
    source_label = models.CharField(max_length=255, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True)
    source_session = models.ForeignKey(
        InterviewSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memory_updates',
    )
    source_document = models.ForeignKey(
        'CandidateDocument',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='memory_facts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'fingerprint'],
                condition=~models.Q(fingerprint=''),
                name='unique_memory_fingerprint_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.get_category_display()}: {self.content[:50]}"


class CandidateDocument(models.Model):
    """Private CV import metadata and parsed text; the uploaded binary is not retained."""

    STATUS_CHOICES = [
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidate_documents')
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)
    mime_type = models.CharField(max_length=120)
    size_bytes = models.PositiveIntegerField()
    content_sha256 = models.CharField(max_length=64)
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='processing')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content_sha256'],
                name='unique_candidate_document_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.user.username})"


class ResumeVersion(models.Model):
    """A saved resume using the canonical, versioned JSON document contract."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resume_versions')
    title = models.CharField(max_length=200)
    target_role = models.CharField(max_length=200, blank=True)
    job_description = models.TextField(blank=True)
    document = models.JSONField(default=dict)
    coverage_percent = models.PositiveSmallIntegerField(default=0)
    source_memory_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class ReadinessSnapshot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='readiness_history')
    session = models.OneToOneField(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name='readiness_snapshot',
    )
    readiness_label = models.CharField(max_length=30, choices=InterviewSession.READINESS_CHOICES)
    dimension_scores = models.JSONField(default=dict, blank=True)
    target_role_gaps = models.JSONField(default=list, blank=True)
    evidence_answer_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
