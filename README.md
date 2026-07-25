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
- PDF/DOCX validation by size, extension, MIME type, file signature, **decompressed size**, and parser
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
- CV-import deletion, complete JSON data export, and password-protected account deletion
- Rate limiting on the endpoints that cost money or send mail (AI calls, CV import, sign-up, password reset)
- All front-end assets self-hosted behind a Content-Security-Policy — nothing loads from a CDN
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
├── .vercelignore
└── interview_prep/            # Vercel Root Directory
    ├── manage.py
    ├── requirements.txt
    ├── vercel.json
    ├── .python-version
    ├── .env.example
    ├── interview_prep/settings.py
    └── prep_app/
        ├── career_views.py
        ├── coach_forms.py
        ├── coach_views.py
        ├── resume_views.py
        ├── security_views.py
        ├── models.py
        ├── middleware.py           # Content-Security-Policy header
        ├── services/
        │   ├── ai_client.py        # shared model-call deadline
        │   ├── career_memory.py
        │   ├── document_parser.py
        │   ├── interview_coach.py
        │   ├── interview_plan.py
        │   ├── rate_limit.py       # DB-backed throttling
        │   └── resume_builder.py
        ├── templates/prep_app/
        └── tests/
```

The large `ai_resume_views.py`, old `ai_resume` templates, and old `resume_exporter.py` are inactive legacy files retained for migration reference. Active URLs do not use their session schema.

## Local setup

Requires Python 3.12, matching `interview_prep/.python-version` and the
deployed runtime.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r interview_prep/requirements.txt
cp interview_prep/.env.example interview_prep/.env
cd interview_prep
python manage.py migrate
python manage.py collectstatic --noinput   # templates resolve assets via {% static %}
python manage.py runserver
```

`DEBUG` defaults to `False` so a deployed environment fails closed. Set
`DEBUG=True` in your local `.env` or the dev server will force HTTPS
redirects and secure-only cookies against `http://localhost`.

For deterministic local development, keep these values in `.env`:

```dotenv
INTERVIEW_COACH_USE_AI=False
CAREER_MEMORY_USE_AI=False
```

The original uploaded CV binary is parsed in memory and not retained. Parsed text is private database data and can be deleted from the Privacy page.

## Tests and verification

From `interview_prep/`:

```bash
../.venv/bin/python manage.py test -v 2
../.venv/bin/python manage.py check
../.venv/bin/python manage.py makemigrations --check --dry-run
../.venv/bin/python -m compileall interview_prep prep_app
```

Production settings check:

```bash
DEBUG=False \
DJANGO_SECRET_KEY='replace-with-at-least-50-random-characters-before-deploy' \
ALLOWED_HOSTS='aceinterview.example.com' \
CSRF_TRUSTED_ORIGINS='https://aceinterview.example.com' \
../.venv/bin/python manage.py check --deploy
```

Dependency audit — expect zero findings:

```bash
pip install pip-audit && ../.venv/bin/python -m pip_audit -r requirements.txt
```

Tests keep authentication, routing, forms, ORM persistence, ownership filters, document parsing, serialization, and exporters real. Only external AI is replaced.

A test that does not fail when you remove the thing it covers is not a test.
The three grounding gates in particular are pinned by negative cases, and two
of them previously were not — the whole suite stayed green with the guard
deleted. When you add or change a guard, delete it, run the suite, confirm it
goes red, then restore.

## Production configuration

`interview_prep/.env.example` documents every supported setting. Important production values:

- `DEBUG=False`
- a long random `DJANGO_SECRET_KEY`
- deployment host in `ALLOWED_HOSTS`
- HTTPS origin in `CSRF_TRUSTED_ORIGINS`
- managed PostgreSQL `DATABASE_URL`
- SMTP host, account, password, and `DEFAULT_FROM_EMAIL`
- Gemini key only when AI extraction/coaching is enabled

Optional, all with safe defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AI_REQUEST_TIMEOUT_SECONDS` | `20` | Per-call deadline for Gemini. The SDK has none of its own, so without this a stalled call runs to the function duration limit instead of falling back. |
| `EMAIL_TIMEOUT` | `10` | Socket timeout for the SMTP send, which happens inside the request. Django's own default is "block forever". |
| `CONTENT_SECURITY_POLICY` | built-in | Overrides the whole CSP header. Leave blank to use the policy in `prep_app/middleware.py`. |

Secure cookies, HSTS, and the HTTPS redirect enable when debug is off, and
database connections are health-checked. `SECURE_PROXY_SSL_HEADER` is set only
when running on Vercel — trusting `X-Forwarded-Proto` is safe only behind a
proxy that overwrites it.

Every front-end asset is committed under `interview_prep/static/` and served
from the app's own origin; a Content-Security-Policy restricts scripts and
styles to `'self'`. Adding a CDN `<script>` or `<link>` will be blocked in the
browser.

## Deployment (Vercel)

The app is deployed as a single Vercel Function on the Python runtime. Vercel
detects Django from `manage.py`, resolves the entrypoint from
`WSGI_APPLICATION`, and runs `collectstatic` during the build, serving the
collected assets from the CDN. WhiteNoise stays in the dependency set because
it is what serves static files locally and under `vercel dev`.

Project settings:

- **Root Directory**: `interview_prep`
- **Python**: 3.12, pinned by `interview_prep/.python-version`
- **Function**: `interview_prep/wsgi.py`, `maxDuration` 120s (`vercel.json`)
- **Database**: Neon Postgres via the Vercel Marketplace, which injects
  `DATABASE_URL` (pooled) and `DATABASE_URL_UNPOOLED` (direct)

Settings refuse to boot on Vercel without `DATABASE_URL`, because the SQLite
fallback lives on a read-only, per-instance filesystem and would silently
discard every account.

Vercel does not run migrations, so a release with a schema change is two
steps — and the order matters. **Migrate first, then deploy.** Additive
migrations are safe against the running old code; deploying first leaves every
request that touches the new table returning 500 until you catch up.

Run both from the **repository root**: the Vercel project link lives there, not
in `interview_prep/`, even though the configured Root Directory is
`interview_prep`. Running these from the subdirectory reports `not_linked`.

```bash
# 1. Apply migrations against the direct endpoint — a transaction-mode
#    pooler cannot carry DDL reliably.
vercel env pull interview_prep/.env.local
cd interview_prep
DATABASE_URL="$(grep -m1 '^DATABASE_URL_UNPOOLED=' .env.local | cut -d= -f2-)" \
  ../.venv/bin/python manage.py showmigrations prep_app   # confirm what is pending
DATABASE_URL="$(grep -m1 '^DATABASE_URL_UNPOOLED=' .env.local | cut -d= -f2-)" \
  ../.venv/bin/python manage.py migrate

# 2. Deploy, from the repo root.
cd .. && vercel --prod
```

The per-deployment `*.vercel.app` URL sits behind Vercel's deployment
protection, so curling it returns Vercel's own login page rather than the app —
useful to know when a smoke test looks wrong. Verify against the stable
production alias instead (`vercel alias ls | grep interviewprep`).

Pushes to `main` build production; every other branch gets a preview URL. The
`.vercel.app` wildcard is added to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
automatically when `VERCEL` is set, because preview hostnames are generated
per commit.

Two runtime constraints follow from serverless hosting: nothing may be written
outside `/tmp`, and no work may outlive the response. Uploads are already
parsed in memory and exports already stream from `io.BytesIO`, so both hold
today — keep it that way.

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
- Request-time Selenium job scraping has been removed. It launched headless Chrome inside the request, which cannot run on a serverless runtime and was never an acceptable production path. Restoring job search means calling a job-board API, not driving a browser in-process.
- Uploads are bounded on decompressed size as well as upload size. A DOCX is a zip archive, so the 10 MB upload limit alone bounds only the compressed bytes — repetitive XML compresses at roughly 1000:1, and a sub-1 MB file that passed every other check could expand to gigabytes during parsing.
- The Django admin registers only `Topic` and `Question`. Candidate data is deliberately absent: the default `ModelAdmin` does no per-owner filtering, so registering it would let one staff credential read every user's CV text and interview answers.
- Every model call carries an explicit deadline and runs outside the database transaction, so a slow provider cannot pin a pooled Postgres connection for the length of an HTTP round trip.
- Dependencies are audited with `pip-audit` and currently report zero known vulnerabilities.

### Known limitations

Honest about what is *not* solved:

- **Password reset does not deliver in production.** The flow is wired and rate limited, but outbound email is parked on purpose — see the "Deferred" section at the top of `TODO.md`. The supported way to change a password is the signed-in form at `/your-profile/`.
- **The CSP still allows `'unsafe-inline'` and `'unsafe-eval'` for scripts.** Several templates carry inline blocks and Alpine evaluates its directives with `new Function`. The origin restriction — the part that stops a third party executing here — is in force; tightening the rest means nonce-ing every inline block and moving to Alpine's CSP build.
- **Registration is still distinguishable.** The error message no longer confirms whether an address is registered, but the response differs between success and failure, so it remains an oracle to anyone willing to script it. Rate limiting is what makes that impractical rather than the message.

Never commit `.env`, databases, personal documents, generated resumes, logs, browser authentication state, or test artifacts.
