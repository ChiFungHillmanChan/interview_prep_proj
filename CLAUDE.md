# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read AGENTS.md first

`AGENTS.md` is the authoritative rulebook for this repo (evidence/honesty rules, Career Memory ownership,
security constraints, testing standard, definition of done). This file covers commands and the
architecture that only becomes visible after reading several files at once. Where the two overlap,
`AGENTS.md` wins.

`README.md` (root) documents the product, deployment, and env vars. `interview_prep/README.md` is a
stale 2024 artifact describing a product that no longer exists — do not treat it as current. The
same is true of everything in `TODO.md` **below** the "Deferred" section at the top; that top
section is current and records work that is parked on purpose.

## Commands

All Django commands run from `interview_prep/` (this is also the Vercel Root Directory).

```bash
cd interview_prep
../.venv/bin/python manage.py runserver
../.venv/bin/python manage.py check
../.venv/bin/python manage.py test -v 2
../.venv/bin/python manage.py makemigrations --check --dry-run   # must report no drift
../.venv/bin/python -m compileall interview_prep prep_app
```

Narrow test runs while iterating:

```bash
../.venv/bin/python manage.py test prep_app.tests.test_interview_coach -v 2
../.venv/bin/python manage.py test prep_app.tests.test_product_flows.CVImportFlowTests -v 2
../.venv/bin/python manage.py test prep_app.tests.test_interview_coach.InterviewCoachFlowTests.test_dashboard_requires_login_and_keeps_career_memory_private -v 2
```

Production settings check:

```bash
DEBUG=False DJANGO_SECRET_KEY='<50+ random chars>' \
ALLOWED_HOSTS='aceinterview.example.com' CSRF_TRUSTED_ORIGINS='https://aceinterview.example.com' \
  ../.venv/bin/python manage.py check --deploy
```

Rebuild the committed Tailwind asset after changing template utility classes (from `interview_prep/`):

```bash
npx --yes tailwindcss@3.4.17 -i static/css/tailwind.input.css -o static/css/tailwind.css --minify \
  --content 'prep_app/templates/**/*.html' 'templates/**/*.html'
```

### Environment gotchas

- `.venv/` is the live Python 3.12 environment (matches `.python-version` and the deployed runtime).
  `env/` is a stale Python 3.11 virtualenv — ignore it.
- `DEBUG` defaults to `False` so deployments fail closed. Without `DEBUG=True` in
  `interview_prep/.env`, the dev server forces HTTPS redirects and secure-only cookies against
  `http://localhost`.
- Keep `INTERVIEW_COACH_USE_AI=False` and `CAREER_MEMORY_USE_AI=False` locally for deterministic runs.
- Vercel does not run migrations. Apply them from a workstation against `DATABASE_URL_UNPOOLED`;
  the transaction-mode pooler cannot carry DDL reliably (see `README.md` for the exact command).

## Architecture

### Two generations of code live side by side

The repo contains a legacy CV/job-analysis app and the current evidence-based coach. They share
`models.py`, `urls.py`, and templates but nothing else.

- **Current stack**: `coach_views.py`, `career_views.py`, `resume_views.py`, `security_views.py`,
  `coach_forms.py`, and everything under `services/` except `ai_integration.py` / `resume_exporter.py`.
- **Legacy but still routed**: `views.py` (~25 KB — home, auth, job/CV analysis, the coding module)
  plus its `forms.py` and `mock_genai.py`. Keep it working, but put no new coach behavior here.
- **Legacy and fully dead**: `ai_resume_views.py` (~85 KB, 91 defs) and everything only it imports —
  `services/ai_integration.py`, `services/resume_exporter.py`, `schemas/`, `templates/ai_resume/`.
  Nothing in `urls.py` reaches them. Do not reconnect their session-based resume schema.
- Root-level `claude.py`, `interface.js`, `template.html`, `question_data.txt` are scratch files
  outside the Django project entirely.

`Topic` / `Question` / `UserSubmission` / `UserCode` belong to the old LeetCode-style coding module.
`/question/<id>/run/` now returns HTTP 410 via `security_views.coding_execution_disabled`; the host
subprocess runner was removed and must not come back without a real isolated sandbox.

### The evidence pipeline

Everything durable flows through `CareerMemoryFact`, and there are **three independent grounding
gates** that stop a model from inventing candidate claims. Understanding them matters more than any
single file:

1. **CV import** — `services/career_memory.py:normalize_items` drops any extracted item whose
   `evidence_excerpt` is not literally present in the whitespace-folded source text, whose category
   is outside `IMPORT_CATEGORIES`, or that duplicates an existing fingerprint.
2. **Interview memory** — `interview_coach._store_memory_updates` requires ≥0.55 token overlap
   between the model's `evidence` string and the candidate's actual answer before persisting.
3. **Skill assessment** — `interview_coach._update_skill_assessments` skips any skill the model
   claims was demonstrated unless the candidate literally named it in the answer.

Facts from CV and interview sources are always created with `user_confirmed=False`,
`review_status='pending'`. Only `user_confirmed=True, review_status='confirmed'` facts feed resumes
and prompt context. Dedup uses `memory_fingerprint(category, title, content)` (SHA-256 of the
normalized triple), enforced by a partial unique constraint on `(user, fingerprint)`.

### AI boundary and fallback

Both `services/interview_coach.py` and `services/career_memory.py` own a private `_request_json`
that returns `None` when AI is disabled, the SDK is missing, the key is empty, or *any* exception
occurs. Every caller has a deterministic fallback (`_fallback_evaluation`, `_fallback_extract`), so
a Gemini outage degrades quality but never breaks the flow. Model JSON is normalized once at that
boundary (`_normalize_result`, `normalize_items`) — clamped scores, enum allow-lists, length caps —
never re-parsed in views or templates.

Tests disable AI with `@override_settings(INTERVIEW_COACH_USE_AI=False)` or patch a single service
method. Do not mock Django auth, routing, the ORM, or ownership filters.

### Interview session state machine

`build_interview_plan(category)` (`services/interview_plan.py`) emits the bounded section list
stored in `InterviewSession.plan_sections`: introduction → experience → role_skills →
core_discussion → follow_ups (×2) → candidate_questions → assessment. `_next_section` advances only
when the answered-turn count for the current section reaches its `question_limit`. Reaching
`assessment` auto-calls `complete_session`, which writes the summary and a `ReadinessSnapshot`.
Model output supplies question *text* only — never section keys. `localize_question` applies the
Cantonese/bilingual prefix at the end of every question path.

### Resume contract

`ResumeVersion.document` is `schema_version: 1`. `TruthfulResumeService.build_document` assembles it
from confirmed facts only; `normalize_saved_document` re-validates every browser-submitted entry —
each factual entry (and each populated personal field) must carry a `memory_id` resolving to a
confirmed fact owned by `request.user`, or the save raises `ValidationError`. Editing text in the
live editor **mutates the underlying `CareerMemoryFact`** into `source_type='manual'` with a new
fingerprint, which is how user edits become explicit evidence. PDF/DOCX exporters
(`CareerResumeExporter`) consume the same saved document and stream from `io.BytesIO`.

### Serverless constraints

Deployed as a single Vercel Function on `interview_prep/wsgi.py` (`maxDuration` 120s). Two rules
follow and both currently hold — keep them holding: nothing may be written outside `/tmp`, and no
work may outlive the response. Uploads are parsed in memory and the binary is never retained
(`CandidateDocument` stores only metadata + extracted text); exports stream from memory. Settings
raise `ImproperlyConfigured` if `DATABASE_URL` is missing while `VERCEL` is set, because the SQLite
fallback would silently discard every account. `*.vercel.app` is appended to `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` automatically on Vercel since preview hostnames are per-commit.

## Conventions worth knowing

- Views are thin: `login_required` + `require_POST` on state changes, `get_object_or_404(..., user=request.user)`
  for every private object, then delegate to a service. There is no DRF layer — `resume_save` is the
  only JSON endpoint and it reads `request.body` directly.
- Redirect targets from user input go through `coach_views._safe_return_url`
  (`url_has_allowed_host_and_scheme` against the current host).
- Templates extend `prep_app/base.html` and use the committed `static/css/tailwind.css` (not a CDN).
  Custom filters live in `templatetags/form_tags.py` (`addclass`, `humanize_key`).
- Uploads are validated by size (10 MB), extension, MIME type, magic bytes (`%PDF` / `PK`), and
  parser success in `services/document_parser.py`.
- Never commit `.env`, `db.sqlite3`, `staticfiles/`, logs, or the personal CVs (`ChiFungHillmanChan.*`)
  sitting untracked in `interview_prep/`. `.vercelignore` re-lists them because CLI deploys ignore
  `.gitignore`.
