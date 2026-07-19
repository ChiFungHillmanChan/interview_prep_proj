"""
AI Integration Service

Handles prompt assembly, validation, and result processing for Gemini API.
Does not make external API calls - provides clean integration points for the host program.
"""

from typing import Tuple, Dict, List
try:
    from ..schemas.ai_resume_schemas import ParsedInputs, AiResult, EditableResume
except ImportError:
    from prep_app.schemas.ai_resume_schemas import ParsedInputs, AiResult, EditableResume
from django.core.exceptions import ValidationError


class AIIntegrationService:
    """
    Service for AI integration without making external calls.
    Provides clean entry points for the host program to handle Gemini API.
    """

    # System prompt - enforces exact template rules and JSON schema
    SYSTEM_PROMPT = """You are an expert resume optimization AI. Your task is to analyze job descriptions and resumes, then generate optimized resume content that follows exact formatting requirements.

CRITICAL REQUIREMENTS:
1. Output ONLY valid JSON that matches the exact schema provided
2. Use strings and arrays of strings only - no null/undefined values
3. All arrays must contain unique non-empty strings
4. coverage_score must be a float between 0.0 and 1.0
5. Dates must be formatted for right-alignment with no wrapping
6. Generate questions_for_user ONLY for job description must-haves that are missing from both resume and notes

TEMPLATE COMPLIANCE:
- Header: Name (bold, 32pt) centered; Role/Title (bold, 19.5pt) centered
- Contact grid: email-left, phone-center, location-right (row 1); GitHub-left, Website-right (row 2)
- Sections: SUMMARY, SKILLS, EDUCATION, EXPERIENCE, PROJECTS (in order)
- Section headings: UPPERCASE with 1px solid black underline
- Experience/Project entries: Title bold left, Date right no-wrap, bullets with hanging indent
- Title may wrap; date must not wrap

ANALYSIS REQUIREMENTS:
- Extract and classify keywords from job description
- Distinguish must-have vs nice-to-have requirements
- Compute accurate coverage score based on resume match to job requirements
- Identify missing keywords that matter for the role
- Provide specific, actionable recommendations
- Generate targeted questions only for critical missing must-haves

RESUME OPTIMIZATION:
- Tailor content to job requirements while maintaining truthfulness
- Optimize keywords and skills for ATS systems
- Structure experience and projects to highlight relevant achievements
- Ensure all content fits the exact template format
- Preserve user's actual experience while optimizing presentation

SKILLS CATEGORIZATION:
- programming: Languages, frameworks, development tools
- database: SQL, NoSQL, data storage technologies
- ai_ml_tools: Machine learning, AI, data science tools
- tools_methodologies: DevOps, project management, methodologies
- soft_skills: Leadership, communication, problem-solving
- additional: Certifications, languages, other relevant skills

Output must be valid JSON matching the exact schema with no additional text or explanations."""

    @classmethod
    def assemble_user_prompt(cls, parsed_inputs: ParsedInputs, user_answers: Dict[str, str] = None) -> str:
        """
        Assemble the user prompt with job description, resume, and optional answers.
        
        Args:
            parsed_inputs: Validated user inputs from Page 1
            user_answers: Optional answers to previous questions_for_user
            
        Returns:
            Complete user prompt string
        """
        user_prompt = f"""Analyze the following job description and resume, then generate optimized resume content.

JOB_DESCRIPTION_TEXT:
```
{parsed_inputs.job_description_text}
```

USER_RESUME_TEXT:
```
{parsed_inputs.resume_text}
```

USER_EXTRA_NOTES:
```
{parsed_inputs.extra_notes or 'None provided'}
```"""

        # Add user answers if provided
        if user_answers:
            answers_text = "\n".join([f"Q: {q}\nA: {a}" for q, a in user_answers.items() if a.strip()])
            if answers_text:
                user_prompt += f"""

ADDITIONAL_USER_ANSWERS:
```
{answers_text}
```"""

        user_prompt += """

TASK:
1. Extract and classify keywords from the job description
2. Analyze the resume against job requirements
3. Compute coverage score (0.0-1.0) based on how well resume matches job
4. Identify missing keywords and provide recommendations
5. Generate optimized resume content following the exact template format
6. Create questions_for_user ONLY for job must-haves missing from both resume and notes

Generate ONLY the JSON response matching the exact schema. No additional text."""

        return user_prompt

    @classmethod
    def get_prompts(cls, parsed_inputs: ParsedInputs, user_answers: Dict[str, str] = None) -> Tuple[str, str]:
        """
        Get system and user prompts for AI processing.
        
        Args:
            parsed_inputs: Validated user inputs
            user_answers: Optional answers to questions
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Validate inputs
        parsed_inputs.validate()
        
        system_prompt = cls.SYSTEM_PROMPT
        user_prompt = cls.assemble_user_prompt(parsed_inputs, user_answers)
        
        return system_prompt, user_prompt

    @classmethod
    def validate_ai_response(cls, ai_json_string: str) -> AiResult:
        """
        Validate and normalize AI JSON response.
        
        Args:
            ai_json_string: Raw JSON string from AI
            
        Returns:
            Validated AiResult object
            
        Raises:
            ValidationError: If JSON is invalid or doesn't match schema
        """
        try:
            result = AiResult.from_json(ai_json_string)
            result.validate()
            return result
        except Exception as e:
            raise ValidationError(f"Invalid AI response: {e}")

    @classmethod
    def merge_user_edits(cls, original_inputs: ParsedInputs, editable_resume: EditableResume, 
                        user_answers: Dict[str, str] = None) -> Tuple[str, str]:
        """
        Merge user edits and answers into a new request for AI refinement.
        
        Args:
            original_inputs: Original parsed inputs from Page 1
            editable_resume: Current state of edited resume
            user_answers: Answers to questions_for_user
            
        Returns:
            Tuple of (system_prompt, user_prompt) for AI refinement
        """
        # Validate inputs
        original_inputs.validate()
        editable_resume.validate()
        
        # Build additional context from user edits
        edit_context = f"""
CURRENT_RESUME_STATE:
Name: {editable_resume.name}
Role: {editable_resume.role}
Summary: {editable_resume.summary}

Skills:
- Programming: {', '.join(editable_resume.skills.programming)}
- Database: {', '.join(editable_resume.skills.database)}
- AI/ML Tools: {', '.join(editable_resume.skills.ai_ml_tools)}
- Tools & Methodologies: {', '.join(editable_resume.skills.tools_methodologies)}
- Soft Skills: {', '.join(editable_resume.skills.soft_skills)}
- Additional: {', '.join(editable_resume.skills.additional)}

Experience Entries: {len(editable_resume.experience)}
Project Entries: {len(editable_resume.projects)}
Education Entries: {len(editable_resume.education)}
Custom Sections: {len(editable_resume.custom_sections)}
"""

        # Create modified inputs with edit context
        modified_inputs = ParsedInputs(
            job_name=original_inputs.job_name,
            job_title=original_inputs.job_title,
            job_description_text=original_inputs.job_description_text,
            resume_text=original_inputs.resume_text,
            extra_notes=original_inputs.extra_notes + "\n\n" + edit_context
        )
        
        return cls.get_prompts(modified_inputs, user_answers)

    @classmethod
    def extract_missing_requirements(cls, ai_result: AiResult, resume_text: str, extra_notes: str) -> List[str]:
        """
        Extract requirements that are missing from both resume and notes.
        Used to generate targeted questions for the user.
        
        Args:
            ai_result: Validated AI result
            resume_text: Original resume text
            extra_notes: User's extra notes
            
        Returns:
            List of missing requirements that should prompt questions
        """
        must_haves = set(req.lower().strip() for req in ai_result.job.must_have)
        combined_text = (resume_text + " " + extra_notes).lower()
        
        missing = []
        for requirement in must_haves:
            # Simple keyword matching - could be enhanced
            if requirement not in combined_text:
                # Check for partial matches of multi-word requirements
                words = requirement.split()
                if len(words) > 1:
                    if not any(word in combined_text for word in words):
                        missing.append(requirement)
                else:
                    missing.append(requirement)
        
        return missing

    @classmethod
    def generate_follow_up_questions(cls, missing_requirements: List[str]) -> List[str]:
        """
        Generate specific questions for missing requirements.
        
        Args:
            missing_requirements: List of missing job requirements
            
        Returns:
            List of targeted questions for the user
        """
        questions = []
        
        for req in missing_requirements[:5]:  # Limit to 5 questions
            if 'year' in req.lower() or 'experience' in req.lower():
                questions.append(f"How many years of experience do you have with {req}?")
            elif 'certification' in req.lower() or 'certified' in req.lower():
                questions.append(f"Do you have any certifications related to {req}?")
            elif 'degree' in req.lower() or 'bachelor' in req.lower() or 'master' in req.lower():
                questions.append(f"What is your educational background related to {req}?")
            else:
                questions.append(f"Do you have experience with {req}? Please provide details.")
        
        return questions

    @classmethod
    def create_refined_prompt(cls, original_result: AiResult, user_answers: Dict[str, str]) -> str:
        """
        Create a refined prompt incorporating user answers to questions.
        
        Args:
            original_result: Original AI result with questions
            user_answers: User's answers to the questions
            
        Returns:
            Refined prompt for AI processing
        """
        if not user_answers:
            return ""
        
        answer_text = []
        for question in original_result.questions_for_user:
            if question in user_answers and user_answers[question].strip():
                answer_text.append(f"Q: {question}\nA: {user_answers[question]}")
        
        if not answer_text:
            return ""
        
        return f"""Please refine the previous resume analysis incorporating these additional details:

{chr(10).join(answer_text)}

Update the resume content, skills, and experience to reflect this new information while maintaining the exact template format."""