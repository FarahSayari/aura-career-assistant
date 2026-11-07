# Aura 2.0 roadmap

This roadmap summarizes the milestone sequence in the preserved
[`Aura_2_0_Project_Hub_Notion.md`](../Aura_2_0_Project_Hub_Notion.md).
The current M0 request supersedes that older reference where scope differs:
Gemini calls and GitHub Actions are deferred, the package structure is `app/` plus
`aura/`, and PostgreSQL is the planned future relational database. No database is
introduced in M0. There are no fixed delivery dates.

## M0 — Project Foundation (implemented)

- Python 3.12 or 3.13 in a project-specific `.venv`.
- Minimal Streamlit homepage with all five career areas marked Coming Soon.
- Pydantic Settings, safe dotenv template, and optional future Gemini credential.
- Pytest configuration and meaningful settings/rendering tests; Ruff checks.
- Setup, architecture, privacy, and roadmap documentation.

Completion means the local application renders, configuration works without API
credentials, and tests and lint checks pass. No API integration, persistence, agent
workflow, CI workflow, commits, or publishing is included in this implementation.

## M1 — Personal profile (planned)

Define a `ProfessionalProfile`, ingest a CV, and let the user review and correct facts
before trusting them. Add career preferences, a cover-letter template, and selected
portfolio/GitHub evidence with attribution. Introduce parsing, AI extraction, retrieval,
and experiment tooling only as the selected slice needs them.

Completion: an accurate, editable, approved profile with source evidence.
The next development task is to agree on the profile schema and review workflow.

## M2 — First working job-fit slice (planned)

Accept a pasted job description, validate a `JobPosting`, compare requirements against
approved profile evidence and preferences, and explain fit and skill gaps. Distinguish
unknown evidence from absent skills. Build a small manually labeled evaluation set.

Completion: meaningful end-to-end assessment of one pasted job; the first usable slice.

## M3 — Tailored applications (planned)

Generate editable cover letters and email drafts from approved evidence and saved
templates. Recommend truthful CV emphasis. Require review before exported content is
treated as approved; evaluate factual grounding and unsupported claims.

Completion: reviewed application drafts for an analyzed job, without invented experience.

## M4 — Application tracking (planned)

Introduce relational persistence for opportunities, statuses, dates, notes, and draft
versions. PostgreSQL is the future database named in the current stack. Add duplicate
warnings and filters. Record actual submissions through user updates.

Completion: a useful application history with editable statuses and saved drafts.

## M5 — Interview preparation (planned)

Create role-specific HR/technical questions, grounded sample answers, mock interviews,
structured feedback, and saved practice sessions. Add LangGraph only for workflows
that benefit from stateful coordination; add LangSmith when tracing such workflows.

Completion: a saved job can launch tailored practice with actionable feedback.

## M6 — Reliability and packaging (planned)

Expand regression evaluations for the AI behavior actually implemented. Use MLflow
for experiments and appropriate tracing for agent behavior; avoid duplicate tracking.
Automate inexpensive tests and lint with GitHub Actions, run paid API evaluations
selectively, and document privacy and operational limitations. Consider Docker only
if it improves repeatability.

Completion: a documented, repeatable personal V1 with evidence for its quality limits.

## Optional expansion after V1

Permitted job-discovery connectors, cited company interview research, career insights,
and safely isolated coding practice may follow. Keep manual job intake usable and
retain user control of external actions. These are options, not M0 commitments.
