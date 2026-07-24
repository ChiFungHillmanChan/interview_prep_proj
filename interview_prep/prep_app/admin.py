from django.contrib import admin
from .models import (
    CareerMemoryFact,
    CareerProfile,
    CandidateDocument,
    InterviewSession,
    InterviewTurn,
    ReadinessSnapshot,
    ResumeVersion,
    SkillEvidence,
    Topic,
    Question,
    UserCode,
    UserSubmission,
)
# Register your models here.
admin.site.register(Topic)
admin.site.register(Question)
admin.site.register(UserCode)
admin.site.register(UserSubmission)
admin.site.register(CareerProfile)
admin.site.register(SkillEvidence)
admin.site.register(InterviewSession)
admin.site.register(InterviewTurn)
admin.site.register(CareerMemoryFact)
admin.site.register(CandidateDocument)
admin.site.register(ResumeVersion)
admin.site.register(ReadinessSnapshot)
