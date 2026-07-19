# AceInterview

AceInterview is an evidence-based personal interview coach. It imports a candidate’s own career evidence, keeps the candidate in control of every durable claim, runs staged adaptive interviews, measures readiness honestly, and produces resumes only from confirmed Career Memory.

The product promise is simple:

> AceInterview remembers your real evidence, interviews you at your demonstrated level, and says when there is not enough evidence.

## Working product flow

```text
PDF/DOCX CV + manual evidence
    → pending Career Memory review
    → inspect / edit / confirm / reject / delete
    → staged adaptive interview
    → complete saved answers + confidence-aware assessment
    → readiness history and target-role gaps
    → confirmed evidence + job description
    → truthful versioned resume
    → live editor → PDF or DOCX
```

Implemented product capabilities:

- Private user-scoped Career Profiles, skills, memory, interviews, uploads, readiness snapshots, and resume versions
- PDF/DOCX validation by size, extension, MIME type, parser, and file signature
- Structured CV extraction for personal details, skills, work experience, projects, education, achievements, certifications, and languages
- Deterministic conservative extraction when Gemini is unavailable
- Evidence-excerpt validation, per-user deduplication, and pending-by-default AI/CV memories
- Confirm, unconfirm, edit, reject, and delete controls for Career Memory
- Modular interview categories: behavioural, technical, coding discussion, system design, graduate, leadership, product, data, and mixed/adaptive
- Stages: introduction → experience → role skills → technical/behavioural → adaptive follow-ups → candidate questions → assessment
- English, Cantonese, bilingual, and English interview with Cantonese feedback modes
- Complete answer persistence, per-skill assessment, confidence, overall readiness, dimension history, and target-role gaps
- Session deletion with an explicit choice about session-generated memories
- Confirmed-only, multi-version resume drafting with 0–100 evidence coverage, missing-requirement questions, live editing, and PDF/DOCX export
- CV-import deletion, complete JSON data export, password-protected account deletion, and working password reset email flow
- Safe local AI fallbacks and strict model-output normalization
- Host code execution disabled until a genuinely isolated sandbox exists

## Evidence and honesty contract

`CareerMemoryFact` is the canonical durable evidence record. Its browser/service contract is:

```json
{
  "schema_version": 1,
  "category": "skill",
  "title": "Python",
  "content": "Python",
  "details": {},
  "evidence_excerpt": "Built a Python scheduling service",
  "source": {"type": "cv", "label": "candidate-cv.docx"},
  "confidence": "high",
  "review_status": "pending"
}
```

Rules enforced in code and tests:

- Model output is never evidence.
- AI/CV facts start unconfirmed.
- Every durable fact retains an evidence excerpt and source.
- Only confirmed memory IDs can enter factual resume sections.
- Resume editor changes become explicit user-provided, confirmed evidence.
- Job requirements without confirmed evidence become growth areas and questions.
- Self-rating, coach assessment, and confidence remain separate.
- Missing assessment evidence is stored and displayed as `null` / “Not enough evidence”.

`ResumeVersion.document` is also versioned (`schema_version: 1`). Factual entries contain a `memory_id`, coverage is always an integer percentage from 0 through 100, and exporters consume the same document saved by the browser editor.

## Project layout

```text
interview_prep_proj/
├── AGENTS.md
├── README.md
├── requirement.txt
├── Procfile
└── interview_prep/
    ├── manage.py
    ├── .env.example
    ├── interview_prep/settings.py
    └── prep_app/
        ├── career_views.py
        ├── coach_forms.py
        ├── coach_views.py
        ├── resume_views.py
        ├── security_views.py
        ├── models.py
        ├── services/
        │   ├── career_memory.py
        │   ├── document_parser.py
        │   ├── interview_coach.py
        │   ├── interview_plan.py
        │   └── resume_builder.py
        ├── templates/prep_app/
        └── tests/
```

The large `ai_resume_views.py`, old `ai_resume` templates, and old `resume_exporter.py` are inactive legacy files retained for migration reference. Active URLs do not use their session schema.

## Local setup

Requires Python 3.11.

```bash
python3.11 -m venv env
source env/bin/activate
python -m pip install --upgrade pip
pip install -r requirement.txt
cp interview_prep/.env.example interview_prep/.env
cd interview_prep
python manage.py migrate
python manage.py runserver
```

For deterministic local development, keep these values in `.env`:

```dotenv
INTERVIEW_COACH_USE_AI=False
CAREER_MEMORY_USE_AI=False
```

The original uploaded CV binary is parsed in memory and not retained. Parsed text is private database data and can be deleted from the Privacy page.

## Tests and verification

From `interview_prep/`:

```bash
../env/bin/python manage.py test -v 2
../env/bin/python manage.py check
../env/bin/python manage.py makemigrations --check --dry-run
../env/bin/python -m compileall interview_prep prep_app
```

Production settings check:

```bash
DEBUG=False \
DJANGO_SECRET_KEY='replace-with-at-least-50-random-characters-before-deploy' \
ALLOWED_HOSTS='aceinterview.example.com' \
CSRF_TRUSTED_ORIGINS='https://aceinterview.example.com' \
../env/bin/python manage.py check --deploy
```

Tests keep authentication, routing, forms, ORM persistence, ownership filters, document parsing, serialization, and exporters real. Only external AI is replaced.

## Production configuration

`interview_prep/.env.example` documents every supported setting. Important production values:

- `DEBUG=False`
- a long random `DJANGO_SECRET_KEY`
- deployment host in `ALLOWED_HOSTS`
- HTTPS origin in `CSRF_TRUSTED_ORIGINS`
- managed PostgreSQL `DATABASE_URL`
- SMTP host, account, password, and `DEFAULT_FROM_EMAIL`
- Gemini key only when AI extraction/coaching is enabled

WhiteNoise serves fingerprinted static assets, secure cookies/HSTS/HTTPS redirect enable when debug is off, proxy HTTPS headers are supported, database connections are health-checked, and Gunicorn is included for deployment.

Start the production web process from the repository root with the included `Procfile`, or directly:

```bash
gunicorn --chdir interview_prep interview_prep.wsgi:application
```

Apply migrations and run `collectstatic --noinput` during each deployment.

When template utility classes change, rebuild the committed Tailwind asset from `interview_prep/`:

```bash
npx --yes tailwindcss@3.4.17 -i static/css/tailwind.input.css -o static/css/tailwind.css --minify --content 'prep_app/templates/**/*.html' 'templates/**/*.html'
```

## Security and privacy

- All Career Memory, upload, interview, answer, readiness, and resume routes require authentication and owner-scoped lookups.
- State changes use POST and CSRF protection.
- Raw CV contents, answers, memory, keys, and model responses are not logged.
- Model JSON is bounded and normalized before persistence.
- Uploaded binaries are never stored.
- Generated exports stream from memory rather than writing personal files to the repository.
- The `/question/<id>/run/` route returns HTTP 410. The old host subprocess implementation has been removed.
- Request-time Selenium job scraping remains legacy and should not be part of the core production path.

Never commit `.env`, databases, personal documents, generated resumes, logs, browser authentication state, or test artifacts.
