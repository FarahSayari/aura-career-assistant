# Aura 2.0 architecture

## M0: a small application with clear boundaries

```text
Streamlit entry point (app/main.py)
                 |
                 v
Validated settings (aura/core/config.py)
                 |
                 v
Environment variables / optional project-root .env / defaults
```

`app/` owns presentation: page layout, descriptions, and Coming Soon placeholders.
The homepage uses native Streamlit columns and bordered containers, allowing the
layout to adapt to smaller screens without custom frontend dependencies. Theme
settings live in `.streamlit/config.toml`; cyan and magenta text accents use native
Streamlit Markdown with the theme's blue and primary colors. Usage telemetry is disabled.
See the [Streamlit theme configuration reference](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
for the native theme options.

`aura/` is the reusable Python package. It currently contains only `core/config.py`.
It does not import Streamlit. Keeping settings and future business logic outside the
UI lets tests exercise behavior without launching a web server and allows future
interfaces to reuse the same logic.

`Settings` validates the application name and environment, loads optional credentials,
and masks the Gemini key through `SecretStr`. It resolves `.env` relative to the
project root, so configuration does not silently change with the working directory.
Constructing settings is explicit; importing a module does not load configuration,
render the page, start a server, or contact a service. The `main()` entry point reads
settings when Streamlit runs the script.

## Packaging and checks

`pyproject.toml` declares Python 3.12–3.13, runtime dependencies, development extras,
package discovery, Pytest settings, and Ruff rules. `requirements.txt` delegates to
the editable project plus its development extras rather than copying version ranges.
Only `aura` is installed as a reusable package; `app/main.py` stays the checkout's
Streamlit entry point. Run it from the repository root after installation.

`tests/test_config.py` checks configuration behavior with isolated environment variables
and temporary dotenv files. `tests/test_app.py` verifies importability and runs the
homepage through Streamlit's built-in `AppTest`. These are deterministic local checks.
No database, service container, API credential, or mocking framework is needed.

All installation and execution happen inside `.venv`. Local runtime downloads and
the preserved previous environment are ignored and are not project dependencies.

## Future integrations: introduce them when behavior needs them

The intended flow is approved personal evidence → verified profile → normalized job
→ explainable fit assessment → reviewed application drafts → application tracking
→ interview practice. This flow describes future work, not implemented M0 behavior.

| Component | Future responsibility | Boundary |
| --- | --- | --- |
| Pydantic models | Professional profile, job requirements, structured outputs | Validate data before using it |
| Gemini API | Language extraction, reasoning, drafting, interview feedback | Dedicated client/service; no UI API calls |
| LangGraph | Stateful workflows and review gates where needed | Plain Python for predictable operations |
| Qdrant | Semantic retrieval over approved evidence | Preserve source references; keep structured facts structured |
| PostgreSQL | Jobs, application state, notes, draft and session history | Persistence layer separate from Streamlit |
| MLflow | Compare prompts/configurations and evaluation results | Add with measurable AI experiments |
| LangSmith | Inspect agent workflows, failures, and latency | Add when agent orchestration exists; redact private data |
| GitHub Actions | Automate lint and deterministic tests | Deferred beyond M0 by the current scope |

Create model, service, retrieval, or persistence modules only as a milestone needs
them. Empty scaffolding, multi-agent abstractions, database connections, model names,
and unused integration dependencies would make the foundation harder to understand.

## Data and trust

Personal documents and secrets stay outside version control. Git ignore patterns are
a guard against accidental additions, not access control or encryption. No personal
information is ingested, persisted, or sent to an API by M0.

Future factual claims must be grounded in user-approved evidence. Missing evidence
must remain distinct from a missing skill. Generated drafts do not indicate that an
application was sent; external actions require explicit user control. Secret masking
does not make logging or publishing complete configuration objects safe.
