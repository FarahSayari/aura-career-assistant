# Aura 2.0 — Agentic AI Career Assistant

Your personal AI companion for smarter job searching.

Aura is a personal, single-user AI engineering project. Its objective is to help you
understand your professional background, evaluate job opportunities, prepare truthful
applications, track progress, and practice interviews. Development proceeds in small,
tested milestones so that each architectural decision stays understandable.

## Current status

**M0 — Project Foundation is implemented.** The application has a responsive Streamlit
homepage, validated configuration, a dark navy/purple theme with cyan and magenta
accents, configuration tests, a UI smoke test, and Ruff configuration.

CV Intelligence, Job Matching, Application Studio, Application Tracking, and Interview
Preparation are all labeled **Coming Soon**. No API calls, document ingestion, database,
agent workflow, or GitHub Actions workflow is implemented. No API key is required.

## Technology stack

| Role | M0 choice |
| --- | --- |
| Language | Python 3.12 or 3.13 |
| Interface | Streamlit |
| Configuration and validation | Pydantic + Pydantic Settings |
| Tests | Pytest + Streamlit's built-in testing utilities |
| Linting and formatting | Ruff |
| Package installation | pip in a project-specific `.venv` |

Future milestones may introduce Gemini, LangGraph, Qdrant, PostgreSQL, MLflow,
LangSmith, and GitHub Actions. Their packages and services are deferred.

## Repository structure

```text
aura-career-assistant/
├── app/
│   └── main.py                 # Streamlit entry point and homepage
├── aura/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       └── config.py           # Typed settings and optional future credentials
├── tests/
│   ├── test_config.py          # Validation, precedence, and secret redaction
│   └── test_app.py             # Import and Streamlit rendering smoke checks
├── docs/
│   ├── architecture.md
│   └── roadmap.md
├── .streamlit/
│   └── config.toml             # Theme and disabled usage telemetry
├── .env.example               # Safe, optional configuration template
├── .gitignore
├── pyproject.toml             # Metadata, dependencies, Pytest and Ruff settings
├── requirements.txt           # Installs the project with development tools
├── LICENSE
├── Aura_2_0_Project_Hub_Notion.md  # Preserved original planning reference
└── README.md
```

## Windows PowerShell setup

Run commands from the repository root. A fresh setup requires an available Python
3.12 or 3.13 interpreter. Check its version before creating an environment; Python
3.11 and 3.14 are outside this project's supported range.

```powershell
Set-Location 'D:\aura 2.0\aura-career-assistant'
python --version
Test-Path .venv

# For a fresh checkout, only when `python` is version 3.12 or 3.13:
python -m venv .venv

# Activate the project environment and verify the selected interpreter:
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -r requirements.txt

# Optional; keep this local file private. M0 works without it.
Copy-Item .env.example .env

python -m streamlit run app/main.py
```

If the Windows `py` launcher is installed, `py -3.13 -m venv .venv` (or `-3.12`)
selects a compatible interpreter explicitly. Otherwise use its full executable path:
`& 'C:\path\to\Python313\python.exe' -m venv .venv`.
Do not recreate a working environment or overwrite an existing `.env` unnecessarily.

**This workspace:** the original system interpreter and `.venv` used Python 3.11.9.
The original environment is preserved in ignored `.venv-py311/`. A standalone Python
3.13.18 runtime was downloaded to ignored `.tools/python/` without changing system
Python, PATH, shell profiles, or the Windows registry; the current `.venv` uses it.
Keep `.tools/python/` while using this environment. To recreate `.venv` with the same
runtime if needed:

```powershell
$auraPython = Get-ChildItem .\.tools\python -Filter python.exe -Recurse |
    Select-Object -First 1 -ExpandProperty FullName
& $auraPython -m venv .venv
```

Activation only changes the current shell's executable lookup. If PowerShell blocks
`Activate.ps1`, you can use the environment directly without changing execution policy:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app/main.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`. Stop the
server with **Ctrl+C**. After an activated session, use `deactivate` to leave `.venv`.

`pyproject.toml` is the single source of dependency declarations. `requirements.txt`
contains `-e .[dev]`, so pip installs the local Aura package in editable mode along
with Pytest and Ruff. Editable installation makes `aura` importable from the Streamlit
entry point without `sys.path` changes. Version ranges constrain supported major
versions; this is not an exact transitive dependency lockfile.

## Configuration and privacy

`Settings` in `aura/core/config.py` uses
[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
to load the project-root `.env` as UTF-8 regardless of the current working directory.
Settings use the `AURA_` prefix:

| Variable | Default | Purpose |
| --- | --- | --- |
| `AURA_APP_NAME` | Aura 2.0 — Agentic AI Career Assistant | Page title and heading |
| `AURA_APP_ENV` | `development` | Validated label: `development`, `test`, or `production` |
| `AURA_GEMINI_API_KEY` | Unset | Optional secret reserved for a future Gemini client |

Explicit constructor values override environment variables, which override `.env`,
which overrides defaults. Empty environment values are ignored. Unrelated dotenv
entries are ignored. No settings instance is created at import time.

The Gemini key uses Pydantic's `SecretStr`, which masks normal representation and JSON
serialization. It is still sensitive: do not display settings dumps, explicitly reveal
keys, or commit credentials. M0 neither validates credentials with Gemini nor uses them.

`.gitignore` excludes local dotenv files, virtual environments, private data folders,
common CV document formats, databases, logs, generated exports, caches, and temporary
files. Store text CVs and other personal material under `private/` or `data/`. Ignore
rules do not remove files already tracked by Git; review `git status` before committing.

## Tests and code quality

These commands always select the project environment, even without activation:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -c "import app.main; from aura.core.config import Settings; print('Imports OK')"
```

Settings tests cover defaults, supported/invalid environments, dotenv loading, override
precedence, blank credentials, and secret redaction. Streamlit's `AppTest` checks that
the homepage renders and shows all five placeholders. No external service is needed.

M0 was validated on Windows with Python 3.13.18: **14 tests passed**, Ruff lint and
format checks passed, application imports succeeded, and `pip check` found no broken
requirements. A temporary headless Streamlit server returned HTTP 200 for both its
health endpoint and homepage. Python 3.12 is supported by the metadata but was not
executed during this validation.

To format changed Python files, run `.\.venv\Scripts\python.exe -m ruff format .`.

## Planned milestones

| Milestone | Outcome | Status |
| --- | --- | --- |
| M0 — Foundation | Local homepage, configuration, environment, tests, documentation | Implemented |
| M1 — Personal profile | Verified profile, preferences, templates, approved evidence | Planned |
| M2 — First job-fit slice | Pasted job, validated requirements, explainable fit and gaps | Planned |
| M3 — Tailored applications | Reviewed, evidence-backed cover letters and email drafts | Planned |
| M4 — Application tracking | Opportunities, statuses, notes, draft history, duplicates | Planned |
| M5 — Interview preparation | Role-specific practice, mock interviews, feedback | Planned |
| M6 — Reliability and packaging | Evaluations, appropriate CI, observability, repeatability | Planned |

Later options include permitted job discovery, company interview research, and career
insights. See [the roadmap](docs/roadmap.md) for scope and
[the architecture](docs/architecture.md) for design decisions. Future work is not part
of M0. The project uses the [MIT license](LICENSE).
