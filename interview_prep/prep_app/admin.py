from django.contrib import admin
from .models import Topic, Question, UserCode, UserSubmission
# Register your models here.
admin.site.register(Topic)
admin.site.register(Question)
admin.site.register(UserCode)
admin.site.register(UserSubmission)