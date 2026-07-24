"""
Mock genai client for testing Resume Builder without AI dependencies
"""
import json
import re

class MockResponse:
    def __init__(self, text):
        self.text = text

class MockClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
    
    class models:
        @staticmethod
        def generate_content(model, contents, config=None):
            """Mock AI response based on the prompt content"""
            
            prompt = contents.lower()
            
            # Mock resume parsing
            if "extract information from this resume" in prompt or "resume parser" in prompt:
                return MockResponse(json.dumps({
                    "contact": {
                        "full_name": "Jane Doe",
                        "email": "jane.doe@example.com",
                        "phone": "+44 20 7946 0100",
                        "address": "Manchester, England",
                        "links": ["https://github.com/example", "example.com"]
                    },
                    "summary": "Data-driven Computer Science with AI graduate with hands-on experience in Python, SQL for data analysis, visualization, and reporting.",
                    "skills": ["Python", "Java", "JavaScript", "React.js", "Node.js", "Django", "MySQL", "MongoDB", "TensorFlow", "PyTorch"],
                    "work_experience": [
                        {
                            "company": "PBM App Team",
                            "title": "Freelance Software Developer",
                            "location": "Hong Kong",
                            "start_date": "Dec 2024",
                            "end_date": "Apr 2025",
                            "bullets": [
                                "Developed cross-platform modules in React Native and TypeScript, improving app load performance by 25% on low-end devices.",
                                "Debugged UI rendering and memory optimization issues, reducing crashes and ensuring stable performance across Android and iOS.",
                                "Participated in Agile sprints and code reviews, ensuring clean, maintainable code."
                            ]
                        },
                        {
                            "company": "Self-Employed",
                            "title": "Programming Tutor",
                            "location": "Hybrid",
                            "start_date": "Jul 2023", 
                            "end_date": "Present",
                            "bullets": [
                                "Taught Python, Java, and software engineering fundamentals with a focus on data structures, algorithms, and debugging strategies.",
                                "Created custom exercises and unit testing frameworks to help students solve real-world coding problems.",
                                "Mentored students through end-to-end projects, emphasizing clean code, performance tuning, and best practices."
                            ]
                        },
                        {
                            "company": "Asda",
                            "title": "Online Service Colleague", 
                            "location": "UK",
                            "start_date": "Jul 2022",
                            "end_date": "Jun 2025",
                            "bullets": [
                                "Collaborated with cross-departmental teams to improve logistics workflows, ensuring smooth coordination between picking, packing, and delivery operations.",
                                "Designed Excel-based inventory check systems with formulas and validation, reducing product discrepancies by 30%.",
                                "Acted as a bridge between operations and management teams to identify issues and implement process optimizations."
                            ]
                        }
                    ],
                    "education": [
                        {
                            "school": "Example University",
                            "degree": "BSc Computer Science with Artificial Intelligence",
                            "field_of_study": "Computer Science with AI", 
                            "year": "Sep 2021 - July 2024",
                            "gpa": "",
                            "honors": ""
                        }
                    ],
                    "certifications": [],
                    "languages": [
                        {
                            "name": "Mandarin",
                            "proficiency": "Fluent"
                        },
                        {
                            "name": "Cantonese", 
                            "proficiency": "Fluent"
                        }
                    ]
                }))
            
            # Mock job description analysis
            elif "analyze" in prompt and ("job description" in prompt or "jd" in prompt):
                return MockResponse(json.dumps({
                    "role": "Software Engineer",
                    "company": "Tech Company",
                    "must_haves": ["Python", "React", "Node.js", "Git", "API Development"],
                    "nice_to_haves": ["Docker", "AWS", "MongoDB"],
                    "keywords": ["software", "development", "engineer", "python", "react", "api"],
                    "seniority": "mid",
                    "key_responsibilities": ["Develop software applications", "Write clean code", "Collaborate with team"]
                }))
            
            # Mock template mapping
            elif "resume-to-template mapper" in prompt:
                return MockResponse(json.dumps({
                    "mapped_content": {
                        "contact_section": {
                            "name": "Jane Doe",
                            "contact_line": "jane.doe@example.com | +44 20 7946 0100 | Manchester, England",
                            "links": ["https://github.com/example", "example.com"]
                        },
                        "summary_section": "Data-driven Computer Science with AI graduate with hands-on experience in Python, SQL for data analysis, visualization, and reporting.",
                        "work_section": [
                            {
                                "company": "PBM App Team",
                                "title": "Freelance Software Developer",
                                "location": "Hong Kong",
                                "date_range": "Dec 2024 - Apr 2025",
                                "bullets": [
                                    "Developed cross-platform modules in React Native and TypeScript, improving app load performance by 25% on low-end devices.",
                                    "Debugged UI rendering and memory optimization issues, reducing crashes and ensuring stable performance across Android and iOS."
                                ]
                            }
                        ],
                        "skills_section": ["Python", "Java", "JavaScript", "React.js", "Node.js", "Django"],
                        "education_section": [
                            {
                                "school": "Example University",
                                "degree_line": "BSc Computer Science with Artificial Intelligence",
                                "year": "Sep 2021 - July 2024"
                            }
                        ],
                        "certifications_section": [],
                        "languages_section": ["Mandarin (Fluent)", "Cantonese (Fluent)"]
                    },
                    "overflow_plan": [],
                    "warnings": []
                }))
            
            # Mock targeted questions
            elif "targeted q&a generator" in prompt:
                return MockResponse(json.dumps([
                    {
                        "id": "skill_docker",
                        "text": "Do you have experience with Docker containers? If yes, how many years and what projects have you used it for?",
                        "expects": "text",
                        "example": "2 years, used in deployment pipelines and microservices"
                    },
                    {
                        "id": "skill_aws",
                        "text": "Have you worked with AWS cloud services? If yes, which services and for how long?",
                        "expects": "text", 
                        "example": "1 year with EC2, S3, and Lambda"
                    }
                ]))
            
            # Mock content tailoring
            elif "resume tailor" in prompt:
                return MockResponse(json.dumps({
                    "updated_work": [
                        {
                            "id": "work_0",
                            "bullets": [
                                {
                                    "text": "Developed cross-platform React Native and TypeScript modules with performance optimizations, improving app load times by 25% on low-end devices using modern JavaScript frameworks",
                                    "evidence_refs": ["original_bullet_0"]
                                },
                                {
                                    "text": "Debugged complex UI rendering and memory optimization issues across Android and iOS platforms, ensuring stable performance and reducing application crashes",
                                    "evidence_refs": ["original_bullet_1"]
                                }
                            ]
                        }
                    ],
                    "skills_add": [],
                    "skills_remove": [],
                    "needs_confirmation": [],
                    "changelog": [
                        "Enhanced React Native bullet to include performance metrics and modern JavaScript framework keywords",
                        "Improved mobile debugging bullet to emphasize cross-platform expertise"
                    ]
                }))
            
            # Default response
            else:
                return MockResponse('{"status": "mock_response", "message": "This is a mock AI response"}')

# Mock the genai module
class genai:
    Client = MockClient