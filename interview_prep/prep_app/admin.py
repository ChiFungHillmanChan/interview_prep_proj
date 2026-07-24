"""Admin registrations.

Only the shared question bank is exposed here. The candidate-data models —
Career Memory, CV imports and their extracted text, interview transcripts and
answers, resumes, skills, readiness history — are deliberately NOT registered.
The default ModelAdmin does no per-owner filtering, so any account with
is_staff could read every user's private evidence, and AGENTS.md forbids
exposing another user's content through "admin-like endpoints".

Users reach their own data through /coach/ and /privacy/, which are scoped to
request.user, and can export or delete all of it from the privacy centre.
"""

from django.contrib import admin

from .models import Question, Topic

admin.site.register(Topic)
admin.site.register(Question)
