from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('prep_app', '0010_remove_resume_user_remove_skill_resume_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CareerProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_role', models.CharField(blank=True, max_length=200)),
                ('goals', models.TextField(blank=True)),
                ('preferred_language', models.CharField(choices=[('english', 'English'), ('cantonese', 'Cantonese'), ('bilingual', 'English + Cantonese')], default='english', max_length=20)),
                ('interview_style', models.CharField(choices=[('supportive', 'Supportive'), ('balanced', 'Balanced'), ('challenging', 'Challenging')], default='balanced', max_length=20)),
                ('desired_difficulty', models.CharField(choices=[('adaptive', 'Adaptive'), ('junior', 'Junior'), ('mid', 'Mid-level'), ('senior', 'Senior')], default='adaptive', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='career_profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='InterviewSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('target_role', models.CharField(max_length=200)),
                ('job_description', models.TextField(blank=True)),
                ('focus_areas', models.JSONField(blank=True, default=list)),
                ('current_question', models.TextField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed')], default='active', max_length=20)),
                ('readiness_label', models.CharField(choices=[('insufficient_evidence', 'Not enough evidence yet'), ('building', 'Building towards the role'), ('mostly_ready', 'Mostly ready'), ('ready', 'Ready to interview')], default='insufficient_evidence', max_length=30)),
                ('summary', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='interview_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SkillEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('self_level', models.CharField(choices=[('unknown', 'Not sure yet'), ('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], default='unknown', max_length=20)),
                ('evidence', models.TextField(blank=True)),
                ('assessment_level', models.CharField(choices=[('not_assessed', 'Not assessed'), ('developing', 'Developing'), ('working', 'Working knowledge'), ('strong', 'Strong evidence')], default='not_assessed', max_length=20)),
                ('assessment_confidence', models.CharField(choices=[('unassessed', 'Not assessed'), ('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='unassessed', max_length=20)),
                ('answers_count', models.PositiveIntegerField(default=0)),
                ('average_score', models.FloatField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='skill_evidence', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='InterviewTurn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question', models.TextField()),
                ('answer', models.TextField()),
                ('feedback', models.TextField()),
                ('scores', models.JSONField(blank=True, default=dict)),
                ('assessment_confidence', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='low', max_length=10)),
                ('demonstrated_skills', models.JSONField(blank=True, default=list)),
                ('next_focus', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='turns', to='prep_app.interviewsession')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='CareerMemoryFact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('experience', 'Experience'), ('strength', 'Strength'), ('growth', 'Growth area'), ('preference', 'Preference'), ('goal', 'Goal')], max_length=20)),
                ('content', models.TextField()),
                ('evidence', models.TextField(blank=True)),
                ('confidence', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], default='low', max_length=10)),
                ('user_confirmed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source_session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='memory_updates', to='prep_app.interviewsession')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='career_memory', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-updated_at']},
        ),
        migrations.AddConstraint(
            model_name='skillevidence',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='unique_skill_per_user'),
        ),
    ]
