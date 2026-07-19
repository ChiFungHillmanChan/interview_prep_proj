# AGENTS.md

These instructions apply to the entire `interview_prep_proj` workspace.

## Product objective

AceInterview is an evidence-based personal interview coach. Its main differentiator is not generic question generation; it remembers a candidate's real career evidence, adapts future interviews, and communicates uncertainty honestly.

The primary product flow is:

```text
Career Profile + Skill Evidence + Target Job + Previous Interview Evidence
    -> Adaptive Question
    -> Candidate Answer
    -> Honest Assessment
    -> User-controlled Career Memory
    -> Next Tailored Question
```

Favor work that makes this vertical slice more reliable before expanding legacy features.

## Working directory and commands

The Django application lives in `interview_prep/`.

```bash
cd interview_prep
../env/bin/python manage.py check
../env/bin/python manage.py test -v 2
../env/bin/python manage.py makemigrations --check --dry-run
```

Use the active environment's Python when `../env/bin/python` is unavailable. Do not assume that a global Python has the required dependencies.

## Architecture boundaries

- `prep_app/coach_views.py`: authenticated HTTP orchestration only
- `prep_app/coach_forms.py`: request validation and form presentation
- `prep_app/services/interview_coach.py`: question generation, assessment normalization, readiness, and memory updates
- `prep_app/services/career_memory.py`: canonical Career Memory contract, CV extraction normalization, and deduplication
- `prep_app/services/interview_plan.py`: modular staged interview plans
- `prep_app/services/resume_builder.py`: confirmed-only resume drafting and portable PDF/DOCX export
- `prep_app/career_views.py`: CV import, privacy, export, and account deletion orchestration
- `prep_app/resume_views.py`: persisted resume-version HTTP orchestration
- `prep_app/models.py`: persistence and domain relationships
- `prep_app/templates/prep_app/coach_*.html`: Career Memory UI
- `prep_app/tests/test_interview_coach.py`: observable coach behavior

Do not add new coach behavior to the legacy `prep_app/views.py`. Create focused services or modules instead. Avoid making `ai_resume_views.py` larger.

## Non-negotiable product rules

### Evidence and honesty

- Never add a skill, achievement, employer, qualification, metric, or project to a user's profile or resume unless it came from user-provided evidence.
- A model suggestion is not evidence.
- Missing requirements must become questions, recommendations, or growth areas—not candidate claims.
- Keep self-assessed level separate from coach-assessed level.
- Use `null` or “Not enough evidence” when a dimension cannot be assessed.
- Store and display assessment confidence. Do not present weak evidence as a precise level.
- Readiness summaries must say what evidence they are based on.

### Career Memory ownership

- All Career Memory, skill, interview, and answer queries must be scoped to `request.user`.
- AI-created memory starts with `user_confirmed=False`.
- Users must be able to inspect, confirm, unconfirm, edit, and delete memory.
- Do not silently reuse deleted memory.
- Do not expose another user's content through URLs, forms, admin-like endpoints, or error messages.

### External AI behavior

- Treat model output as untrusted input.
- Request structured JSON and normalize every field before persistence.
- Clamp numeric ranges and reject unsupported enum values.
- Do not let model output select database object IDs, URLs, templates, or filesystem paths.
- Keep a deterministic, honest fallback so an API failure does not break interview practice.
- Tests must not call external AI services. Replace only the model boundary; keep owned Django wiring real.

## Security rules

- Never execute user-submitted code directly on the Django host.
- `prep_app.views.run_code` is known unsafe legacy code. Do not extend or deploy it. Any replacement requires a disposable sandbox with CPU, memory, process, filesystem, and network isolation.
- Never log API keys, `.env` values, raw CV contents, full interview answers, or Career Memory.
- Require authentication for all private candidate data.
- Preserve CSRF protection on state-changing requests.
- Validate uploaded files by size, extension, MIME type, and parser; never trust the filename alone.
- Avoid open redirects. Validate user-supplied return URLs against the current host.
- Do not put personal CVs, generated documents, databases, logs, or browser authentication state into source control.

## Data and migrations

- Create a migration for every model change.
- Run `makemigrations --check --dry-run` after editing models; it must report no missing migration.
- Do not edit an already-applied migration unless the project has not been shared and the user explicitly asks for it.
- JSON fields crossing the browser, session, AI, and exporter boundaries must have one canonical documented shape.
- Prefer explicit models for durable, queryable evidence. Use JSON only for bounded structures such as score maps and focus lists.

## Testing standard

Write tests around user-visible behavior and meaningful persisted outcomes.

Required coverage for coach changes includes the relevant subset of:

- Authentication requirement
- Cross-user isolation
- Form validation
- Interview state transition
- Adaptive next question
- Answer and feedback persistence
- Skill evidence update
- Prevention of model-invented skill updates
- Memory confirmation and deletion
- Honest insufficient-evidence behavior
- Session completion and readiness summary
- External AI failure fallback

Mock only nondeterministic or external boundaries. Do not mock Django authentication, routing, ORM persistence, or ownership filters in integration tests. A test should fail if the user-facing rule breaks, even if internal helper names change.

Run the narrow coach tests first when iterating:

```bash
cd interview_prep
../env/bin/python manage.py test prep_app.tests.test_interview_coach -v 2
```

Then run the full suite before handoff.

## UI/UX conventions

- Preserve the existing AceInterview blue-and-white visual language.
- Reuse the base template, Tailwind spacing, rounded cards, subtle borders, and blue primary actions.
- Keep the interview question and answer action visually dominant.
- Show self-rating, coach assessment, and confidence as separate labels.
- Always provide a plain-language explanation alongside scores.
- Keep forms usable on narrow mobile screens; verify important pages at desktop and phone widths.
- Do not hide uncertainty, privacy controls, or destructive memory actions.
- Avoid adding a new frontend framework unless the user explicitly requests a redesign.

## Code style

- Keep views thin and services focused.
- Prefer descriptive domain names over generic `data`, `result`, or `process` when the scope is unclear.
- Add type hints to service boundaries where they improve the contract.
- Normalize model output once at the boundary rather than repeatedly throughout views and templates.
- Avoid broad exception handling unless it is at an external boundary with a safe fallback.
- Do not print PII or debug model responses.
- Preserve unrelated user changes.

## Canonical data contracts

- `CareerMemoryFact` is the durable evidence contract. Every fact has a category, content, evidence excerpt, source type/label, confidence, review status, and optional source document/session.
- CV and AI-created facts always start `review_status=pending` and `user_confirmed=False`.
- `ResumeVersion.document` uses `schema_version=1`; every factual section entry retains a confirmed Career Memory ID. Coverage is always an integer percentage from 0 to 100.
- Interview plans are JSON lists of bounded section descriptors created only by `services/interview_plan.py`; model output never chooses section keys.

## Known technical debt

- `prep_app/views.py` and `prep_app/ai_resume_views.py` are oversized and contain legacy paths.
- `ai_resume_views.py`, its old templates, and `services/resume_exporter.py` remain as inactive legacy code. Active URLs use the canonical persisted builder; do not reconnect the legacy session schema.
- Job scraping uses request-time Selenium and should not be part of the core product path.
- Coding execution is disabled. Do not reconnect host subprocess execution; a future runner needs a disposable isolated sandbox.

Do not quietly work around these issues in new coach code. Isolate new work from them or fix them explicitly with regression tests.

## Definition of done

Before declaring a change complete:

1. The requested user journey works through real Django routes and persistence.
2. Candidate claims remain grounded in user evidence.
3. Ownership and authentication are enforced.
4. External AI failure has a safe behavior.
5. Relevant behavior tests pass.
6. `manage.py check` passes.
7. Migration drift check passes.
8. Material UI changes are checked at desktop and mobile widths.
9. No secret, authentication state, personal document, database, or generated runtime artifact was added.
