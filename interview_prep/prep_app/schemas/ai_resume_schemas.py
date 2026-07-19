"""
AI Resume Builder Data Schemas

Defines the exact data contracts for AI integration and internal objects.
Validates JSON schema compliance and provides type-safe data structures.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import json
from django.core.exceptions import ValidationError


@dataclass
class JobKeywords:
    """Job keywords classification"""
    hard_skills: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    certs: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)

    def validate(self):
        """Ensure all arrays contain unique non-empty strings"""
        for attr_name in ['hard_skills', 'soft_skills', 'tools', 'certs', 'domains']:
            items = getattr(self, attr_name)
            if not isinstance(items, list):
                raise ValidationError(f"{attr_name} must be a list")
            
            # Remove duplicates and empty strings
            unique_items = list(dict.fromkeys([str(item).strip() for item in items if str(item).strip()]))
            setattr(self, attr_name, unique_items)


@dataclass
class Job:
    """Job description analysis"""
    title: str = ""
    seniority: str = ""
    keywords: JobKeywords = field(default_factory=JobKeywords)
    must_have: List[str] = field(default_factory=list)
    nice_to_have: List[str] = field(default_factory=list)

    def validate(self):
        """Validate job data"""
        self.title = str(self.title).strip()
        self.seniority = str(self.seniority).strip()
        self.keywords.validate()
        
        # Ensure unique non-empty strings
        self.must_have = list(dict.fromkeys([str(item).strip() for item in self.must_have if str(item).strip()]))
        self.nice_to_have = list(dict.fromkeys([str(item).strip() for item in self.nice_to_have if str(item).strip()]))


@dataclass
class Analysis:
    """Resume coverage analysis"""
    coverage_score: float = 0.0
    missing_keywords: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def validate(self):
        """Validate analysis data"""
        # Ensure coverage_score is between 0.0 and 1.0
        try:
            self.coverage_score = float(self.coverage_score)
            if not (0.0 <= self.coverage_score <= 1.0):
                raise ValidationError("coverage_score must be between 0.0 and 1.0")
        except (ValueError, TypeError):
            raise ValidationError("coverage_score must be a valid float")
        
        # Ensure unique non-empty strings
        self.missing_keywords = list(dict.fromkeys([str(item).strip() for item in self.missing_keywords if str(item).strip()]))
        self.recommendations = list(dict.fromkeys([str(item).strip() for item in self.recommendations if str(item).strip()]))


@dataclass
class Contacts:
    """Contact information in simple format compatible with live preview template"""
    email: str = ""
    phone: str = ""
    location: str = ""
    github: str = ""
    website: str = ""

    def validate(self):
        """Validate contact data"""
        self.email = str(self.email).strip()
        self.phone = str(self.phone).strip()
        self.location = str(self.location).strip()
        self.github = str(self.github).strip()
        self.website = str(self.website).strip()


@dataclass
class Skills:
    """Skills categorization"""
    programming: List[str] = field(default_factory=list)
    database: List[str] = field(default_factory=list)
    ai_ml_tools: List[str] = field(default_factory=list)
    tools_methodologies: List[str] = field(default_factory=list)
    soft_skills: List[str] = field(default_factory=list)
    additional: List[str] = field(default_factory=list)

    def validate(self):
        """Ensure all skill arrays contain unique non-empty strings"""
        for attr_name in ['programming', 'database', 'ai_ml_tools', 'tools_methodologies', 'soft_skills', 'additional']:
            items = getattr(self, attr_name)
            if not isinstance(items, list):
                raise ValidationError(f"{attr_name} must be a list")
            
            # Remove duplicates and empty strings
            unique_items = list(dict.fromkeys([str(item).strip() for item in items if str(item).strip()]))
            setattr(self, attr_name, unique_items)


@dataclass
class Education:
    """Education entry"""
    degree_bold: str = ""
    institution_bold: str = ""
    dates_left: str = ""
    location_right: str = ""

    def validate(self):
        """Validate education data"""
        self.degree_bold = str(self.degree_bold).strip()
        self.institution_bold = str(self.institution_bold).strip()
        self.dates_left = str(self.dates_left).strip()
        self.location_right = str(self.location_right).strip()


@dataclass
class ExperienceProject:
    """Experience or Project entry"""
    title_bold_left: str = ""
    date_right_nowrap: str = ""
    bullets: List[str] = field(default_factory=list)

    def validate(self):
        """Validate experience/project data"""
        self.title_bold_left = str(self.title_bold_left).strip()
        self.date_right_nowrap = str(self.date_right_nowrap).strip()
        
        # Ensure unique non-empty bullets
        self.bullets = list(dict.fromkeys([str(bullet).strip() for bullet in self.bullets if str(bullet).strip()]))


@dataclass
class CustomSection:
    """User-defined custom section"""
    heading: str = ""
    bullets: List[str] = field(default_factory=list)

    def validate(self):
        """Validate custom section data"""
        self.heading = str(self.heading).strip()
        self.bullets = list(dict.fromkeys([str(bullet).strip() for bullet in self.bullets if str(bullet).strip()]))


@dataclass
class Resume:
    """Complete resume data structure"""
    name: str = ""
    role: str = ""
    contacts: Contacts = field(default_factory=Contacts)
    summary: str = ""
    skills: Skills = field(default_factory=Skills)
    education: List[Education] = field(default_factory=list)
    experience: List[ExperienceProject] = field(default_factory=list)
    projects: List[ExperienceProject] = field(default_factory=list)

    def validate(self):
        """Validate entire resume structure"""
        self.name = str(self.name).strip()
        self.role = str(self.role).strip()
        self.summary = str(self.summary).strip()
        
        self.contacts.validate()
        self.skills.validate()
        
        for edu in self.education:
            edu.validate()
        for exp in self.experience:
            exp.validate()
        for proj in self.projects:
            proj.validate()


@dataclass
class AiResult:
    """Complete AI output schema - validates exact JSON structure"""
    job: Job = field(default_factory=Job)
    analysis: Analysis = field(default_factory=Analysis)
    resume: Resume = field(default_factory=Resume)
    questions_for_user: List[str] = field(default_factory=list)

    def validate(self):
        """Validate complete AI result"""
        self.job.validate()
        self.analysis.validate()
        self.resume.validate()
        
        # Ensure unique non-empty questions
        self.questions_for_user = list(dict.fromkeys([str(q).strip() for q in self.questions_for_user if str(q).strip()]))

    @classmethod
    def from_json(cls, json_str: str) -> 'AiResult':
        """Create AiResult from JSON string with validation"""
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AiResult':
        """Create AiResult from dictionary with validation"""
        # Validate required top-level keys
        required_keys = {'job', 'analysis', 'resume', 'questions_for_user'}
        if not isinstance(data, dict):
            raise ValidationError("AI result must be a dictionary")
        
        # Check for extra keys
        extra_keys = set(data.keys()) - required_keys
        if extra_keys:
            raise ValidationError(f"Unexpected keys in AI result: {extra_keys}")

        try:
            # Build nested structures
            job_data = data.get('job', {})
            job_keywords = JobKeywords(**job_data.get('keywords', {}))
            job = Job(
                title=job_data.get('title', ''),
                seniority=job_data.get('seniority', ''),
                keywords=job_keywords,
                must_have=job_data.get('must_have', []),
                nice_to_have=job_data.get('nice_to_have', [])
            )

            analysis = Analysis(**data.get('analysis', {}))

            resume_data = data.get('resume', {})
            contacts = Contacts(**resume_data.get('contacts', {}))
            skills = Skills(**resume_data.get('skills', {}))
            
            education = [Education(**edu) for edu in resume_data.get('education', [])]
            experience = [ExperienceProject(**exp) for exp in resume_data.get('experience', [])]
            projects = [ExperienceProject(**proj) for proj in resume_data.get('projects', [])]

            resume = Resume(
                name=resume_data.get('name', ''),
                role=resume_data.get('role', ''),
                contacts=contacts,
                summary=resume_data.get('summary', ''),
                skills=skills,
                education=education,
                experience=experience,
                projects=projects
            )

            result = cls(
                job=job,
                analysis=analysis,
                resume=resume,
                questions_for_user=data.get('questions_for_user', [])
            )

            # Validate the complete structure
            result.validate()
            return result

        except (TypeError, KeyError, AttributeError) as e:
            raise ValidationError(f"Invalid AI result structure: {e}")


@dataclass
class EditableResume:
    """Mutable copy of AiResult.resume with custom sections"""
    name: str = ""
    role: str = ""
    contacts: Contacts = field(default_factory=Contacts)
    summary: str = ""
    skills: Skills = field(default_factory=Skills)
    education: List[Education] = field(default_factory=list)
    experience: List[ExperienceProject] = field(default_factory=list)
    projects: List[ExperienceProject] = field(default_factory=list)
    custom_sections: List[CustomSection] = field(default_factory=list)

    @classmethod
    def from_resume(cls, resume: Resume) -> 'EditableResume':
        """Create EditableResume from Resume"""
        return cls(
            name=resume.name,
            role=resume.role,
            contacts=resume.contacts,
            summary=resume.summary,
            skills=resume.skills,
            education=resume.education.copy(),
            experience=resume.experience.copy(),
            projects=resume.projects.copy(),
            custom_sections=[]
        )

    def to_resume(self) -> Resume:
        """Convert back to Resume (without custom sections)"""
        return Resume(
            name=self.name,
            role=self.role,
            contacts=self.contacts,
            summary=self.summary,
            skills=self.skills,
            education=self.education,
            experience=self.experience,
            projects=self.projects
        )

    def validate(self):
        """Validate editable resume"""
        self.name = str(self.name).strip()
        self.role = str(self.role).strip()
        self.summary = str(self.summary).strip()
        
        self.contacts.validate()
        self.skills.validate()
        
        for edu in self.education:
            edu.validate()
        for exp in self.experience:
            exp.validate()
        for proj in self.projects:
            proj.validate()
        for section in self.custom_sections:
            section.validate()


@dataclass
class ParsedInputs:
    """User inputs from Page 1"""
    job_name: str = ""
    job_title: str = ""
    job_description_text: str = ""
    resume_text: str = ""
    extra_notes: str = ""

    def validate(self):
        """Validate parsed inputs"""
        self.job_name = str(self.job_name).strip()
        self.job_title = str(self.job_title).strip()
        self.job_description_text = str(self.job_description_text).strip()
        self.resume_text = str(self.resume_text).strip()
        self.extra_notes = str(self.extra_notes).strip()