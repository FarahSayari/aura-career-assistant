# Aura 2.0 — Agentic AI Career Assistant

Your personal AI companion for smarter job searching.

Aura is a personal, single-user AI engineering project. Its objective is to help you
understand your professional background, evaluate job opportunities, prepare truthful
applications, track progress, and practice interviews. Development proceeds in small,
tested milestones so that each architectural decision stays understandable.

The immediate goal is **Prototype 1: a functional LangGraph career assistant based on
the notebook**, with CV/job intake, explainable comparisons, conversational
follow-ups, LangSmith tracing, basic AI evaluation, and Streamlit Community Cloud
deployment. See the [current roadmap](docs/roadmap.md) for scope and completion criteria.
This is the development direction; the current implementation is described below.

## Current status

**M0, M1.1, M1.2a, and M1.2b are implemented.** Aura includes a themed Streamlit homepage,
validated configuration, ProfessionalProfile schemas, local PDF text extraction, and
explicitly consented Gemini extraction into an **Unverified** structured profile.

Job Matching, Application Studio, Application Tracking, and Interview Preparation remain
**Coming Soon** in Streamlit. OCR, portfolio ingestion, profile verification, databases,
and GitHub Actions remain unimplemented. Local PDF parsing requires no API key. Gemini
analysis requires a configured key/model, explicit confirmation, and an analysis click.

**P1.1 core agent is implemented and verified offline.** The notebook's explicit
LangGraph loop and two tools are available through a local runner, using a configurable
Gemini candidate, one PDF, one pasted job description, and follow-up memory. Live
Gemini access and reasoning quality are not yet established. Streamlit agent chat,
URL retrieval, and configured LangSmith tracing remain planned.

## Technology stack

| Role | Current choice |
| --- | --- |
| Language | Python 3.12 or 3.13 |
| Interface | Streamlit |
| Configuration and validation | Pydantic + Pydantic Settings |
| Local PDF parsing | PyMuPDF |
| Structured CV extraction | Gemini API through the official `google-genai` SDK |
| Career agent | Explicit LangGraph graph with a LangChain Gemini model adapter |
| Notebook-compatible PDF reader | pdfplumber; separate from the existing PyMuPDF service |
| Tests | Pytest + Streamlit's built-in testing utilities |
| Linting and formatting | Ruff |
| Package installation | pip in a project-specific `.venv` |

LangGraph is integrated into the P1.1 core. LangSmith is installed as a framework
dependency, but tracing is explicitly disabled until privacy controls are introduced
in P1.4. Gemini is the initial agent-model candidate; live model evaluation and job
retrieval remain planned. Qdrant, PostgreSQL, MLflow, and GitHub Actions are deferred.

## Repository structure

```text
aura-career-assistant/
├── app/
│   ├── main.py                 # Streamlit entry point and homepage
│   └── pages/
│       └── cv_intelligence.py  # Local preview and consent-controlled Gemini analysis
├── aura/
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── __main__.py        # Explicit local runner; no Streamlit chat yet
│   │   ├── graph.py           # Assistant/tools loop, memory, limits, and safe errors
│   │   ├── model.py           # Configurable Gemini tool-calling candidate
│   │   └── tools.py           # Notebook reader and pasted-job evidence tools
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py           # Typed settings and optional future credentials
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── professional_profile.py  # Professional facts, sources, and review states
│   │   └── cv_extraction.py    # Untrusted model output without trust metadata
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── cv_extraction_v1.py # Versioned factual extraction instructions
│   │   └── career_agent_v1.py # Grounded comparison and follow-up instructions
│   └── services/
│       ├── __init__.py
│       ├── pdf_extraction.py   # In-memory parsing and page/block metadata
│       ├── gemini_extraction.py # API boundary, structured validation, safe errors
│       └── profile_conversion.py # Application-owned provenance and unverified states
├── tests/
│   ├── conftest.py             # In-memory synthetic PDF factory
│   ├── test_config.py          # Validation, precedence, and secret redaction
│   ├── test_app.py             # Homepage, upload flow, text previews, and errors
│   ├── test_professional_profile.py
│   ├── test_pdf_extraction.py  # Synthetic PDFs, errors, layout, and size limits
│   ├── test_pdf_reading_order.py
│   ├── test_gemini_extraction.py # Mocked SDK, trust boundaries, local HTTP contract
│   ├── test_agent_tools.py    # Notebook PDF reader and parser comparison
│   ├── test_career_agent.py   # Real graph with scripted model responses
│   ├── test_agent_model.py    # Adapter configuration and mocked HTTP integration
│   └── test_agent_runner.py   # Consent and local conversation lifecycle
├── evals/
│   └── cv_extraction_baseline.json # Synthetic CV texts and expected factual results
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

# Optional; keep this local file private. Aura works without it.
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
| `AURA_GEMINI_API_KEY` | Unset | Required only for explicitly requested Gemini analysis |
| `AURA_GEMINI_MODEL` | `gemini-2.5-flash` | Stable model ID enabled for your Gemini API project |
| `AURA_AGENT_MODEL` | `gemini-3.5-flash-lite` | Provisional tool-calling candidate, separate from structured extraction |
| `AURA_AGENT_MAX_MODEL_CALLS` | `6` | Maximum model requests per conversation turn, between 2 and 12 |
| `AURA_AGENT_MAX_TURNS` | `10` | Maximum successful turns before reset, between 1 and 20 |
| `AURA_PDF_MAX_SIZE_MB` | `10` | Positive integer PDF size limit in MiB, enforced before parsing |

Explicit constructor values override environment variables, which override `.env`,
which overrides defaults. Empty environment values are ignored. Unrelated dotenv
entries are ignored. No settings instance is created at import time.

The Gemini key uses Pydantic's `SecretStr`, which masks normal representation and JSON
serialization. It is still sensitive: do not display settings dumps, explicitly reveal
keys, or commit credentials. No credentials are checked remotely before an explicitly
confirmed analysis request. Secrets are never included in user-facing error details.

`.gitignore` excludes local dotenv files, virtual environments, private data folders,
common CV document formats, databases, logs, generated exports, caches, and temporary
files. Store text CVs and other personal material under `private/` or `data/`. Ignore
rules do not remove files already tracked by Git; review `git status` before committing.

## Try CV PDF extraction

After pulling these source changes, install the updated dependencies inside `.venv`:

```powershell
Set-Location 'D:\aura 2.0\aura-career-assistant'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app/main.py
```

1. Open the local URL printed by Streamlit, normally `http://localhost:8501`.
2. Select **CV Intelligence** in the sidebar or click **Open CV Intelligence** on Home.
3. Upload a PDF with selectable text, within the default **10 MiB** limit.
4. Click **Extract document text**.
5. Inspect page count, file size, embedded PDF metadata, and each numbered page's text.

The **Extract document text** action runs locally in memory without external services.
Extracted text is shown as read-only text, not interpreted as Markdown or AI analysis.
Changing or removing the upload clears the old preview and requires a new extraction
action. There is no shared cache, saved profile, or document persistence. Removing the
upload releases its widget reference; Streamlit manages session-memory cleanup.

The reusable `extract_pdf_text(pdf_bytes, max_size_mb=10)` service in
`aura/services/pdf_extraction.py` returns numbered pages, text blocks and their bounding
boxes/original indices, dimensions, file size, metadata, and a repair flag. Its combined
`text` property separates pages with a form-feed character (`\f`). Normalization removes
trailing whitespace and excess blank lines while retaining line breaks, indentation,
and internal spacing. Where geometric evidence supports two or three separate columns,
blocks are read left-to-right by column, each top-to-bottom, rather than interleaving
every block by vertical position. Spanning headings/paragraphs separate vertical sections
before column ordering. The parser closes its document even if extraction fails and
does not log document content or native parser diagnostics.

Empty files, invalid or unreadable PDFs, encrypted PDFs, oversized uploads, and documents
with no extractable text produce useful errors. Encryption is rejected even when no
user password is required; password entry is not part of this milestone. Some damaged
PDFs can be repaired by PyMuPDF; successful recovery is flagged for review. A blank or
image-only page in an otherwise readable document retains its original page number and
shows a warning instead of being silently dropped.

**Layout strategy and fallback:** repeated left edges, clear gutters, multiple text lines
per column, and overlapping vertical ranges support column detection. A block crossing
a gutter acts as a section divider only when vertically separate from the other text.
Sparse or overlapping layouts, unsupported column arrangements, rotated text, or
side-by-side lines already merged into one PyMuPDF block retain the original
position-sorted extraction. The page displays a warning rather than splitting blocks
or guessing. `PdfPage.layout_warning` exposes that limitation to service callers;
existing page fields and embedded metadata remain intact.

A mixed-layout page may contain a compact column section plus right-aligned labels
elsewhere. If page-wide detection fails, Aura can recover a local section anchored by
two side-by-side multiline blocks with closely matching top and bottom edges. Only
that contiguous region is reordered. Its gutter threshold scales with estimated text
line height (at least 2 PDF points), allowing narrow but non-overlapping columns.
Overlapping content, competing regions, or a close continuation outside the region
prevent recovery. The page notice distinguishes local recovery from full fallback;
text and ordering outside a recovered region remain unchanged.

For example, the original order `A heading → B heading → A continuation → B continuation`
becomes `A heading → A continuation → B heading → B continuation` when columns are clear.
No section names, technologies, or personal content are used to decide the order.

**Limitations:** these geometric rules do not establish semantic reading order. Tables,
unusual fonts, missing text encodings, short headings whose visual span is not encoded,
and changing/irregular layouts may still be ambiguous or go undetected. The strategy
assumes left-to-right columns and supports at most three; it does not reconstruct text
already merged across columns. Page numbers and block coordinates are preserved, and
Aura does not evaluate whether a claim is true. Scanned or
image-only PDFs require OCR, which is not implemented. A scan containing only a small
selectable header can return that header without the image's contents; review every page
against the original CV. Embedded metadata is supplied by the PDF and is not verified.
See [PyMuPDF's text extraction guidance](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)
for the underlying reading-order limitations.

To change the limit, set `AURA_PDF_MAX_SIZE_MB=5` in the local `.env` or current shell and
restart/rerun the application. The setting controls both the upload widget and the service.

## Configure and try Gemini structured extraction

Create an API key for your Gemini API project using the
[Google API key guide](https://ai.google.dev/gemini-api/docs/api-key). Edit your ignored
local `.env` (copy `.env.example` first only if `.env` does not already exist):

```dotenv
AURA_GEMINI_API_KEY=replace_with_your_real_key_locally
AURA_GEMINI_MODEL=gemini-2.5-flash
```

`gemini-2.5-flash` is the requested default. Availability is specific to the configured
project and was not checked with a live API call during development. If the API reports
the model unavailable, choose a stable model enabled for your project and update
`AURA_GEMINI_MODEL`. Aura does not silently switch models, providers, or billing projects.
See Google's [model documentation](https://ai.google.dev/gemini-api/docs/models) and
[deprecation schedule](https://ai.google.dev/gemini-api/docs/deprecations).

1. Install the updated dependencies and launch Streamlit using the commands above.
2. Open **CV Intelligence**, upload a PDF, and click **Extract document text**.
3. Review the local preview and any reading-order warnings.
4. Read the Google transmission notice and select the confirmation checkbox.
5. Click **Analyze with Gemini**. Checking the box alone sends nothing.
6. Inspect the **Professional profile — Unverified** JSON and compare every claim
   against the CV. No approval, editing, verification, or save operation is implemented.

The service sends ordered text blocks, coordinates, page numbers, and layout warnings
as a JSON data payload to Google. It does not send the PDF binary, embedded PDF metadata,
or local filename. The text may include your name, email, phone, and other personal facts.
Review [Gemini API terms and data handling](https://ai.google.dev/gemini-api/terms) for
your project before confirming. API costs, quota, retention, and provider-side use are
governed by Google's applicable service terms; Aura cannot guarantee remote deletion.
Google's unpaid-service terms permit product-improvement use and human review and
instruct users to keep personal/confidential material out of those services; paid-service
handling differs. Check the applicable project plan before analyzing a personal CV.
Do not enable verbose SDK/HTTP debug logging when processing personal documents.

The application keeps local text and analysis results only in Streamlit session memory,
without shared caches or disk persistence. Changing/removing the upload clears the PDF
preview, structured result, and confirmation; the replacement document requires fresh
extraction and consent. A normal rerun never repeats an analysis request automatically.

The versioned prompt asks for supported facts, original skill categories, partial dates,
and explicit project/feature states, with no invented facts or duplicate records. CV
instructions are treated as untrusted data. The extraction-specific `CvExtraction`
schema exposes only factual fields; extra fields such as `verification_status`, `sources`,
or `career_preferences` are rejected. The application validates the returned JSON, then
converts it into a new `ProfessionalProfile`, assigning CV references and explicitly
setting every professional record to `unverified`. Existing profiles are never passed
to Gemini or overwritten. Preferences remain `None`.

References identify the input document and page range. **Exact fact-to-page attribution
is not resolved**, and a reference does not prove that a claim is supported. JSON Schema
validation verifies shape and domain constraints, not truth. Gemini may still omit,
duplicate, misgroup, or hallucinate information; the prompt does not guarantee factual
accuracy or eliminate prompt injection. Unknown facts and unspecified statuses stay
unknown in the schema. Human review remains necessary.

Each analysis makes one request with a 60-second timeout and an 8,192-token output limit.
Automatic SDK retries are disabled. Missing key/model, access denial, unavailable models,
quota/rate limits, transport failures, blocked/truncated responses, invalid JSON, and
validation failures produce predefined messages without raw sensitive details. Failed
responses are not accepted as profiles; another click may incur another request.

## Try the P1.1 career agent locally

P1.1 ports the notebook's graph into Python modules. The existing Streamlit pages
are preserved; the agent's Streamlit chat interface is planned for P1.3. This step
accepts one PDF and one pasted job description, without URL retrieval or OpenAI calls.

Prepare a synthetic selectable-text CV PDF and a UTF-8 text file containing a job
description under ignored `private/`. Keep these inputs local. Configure your ignored
`.env` with `AURA_GEMINI_API_KEY` and a tool-calling `AURA_AGENT_MODEL` enabled in your
project. The default is a candidate, not a benchmark winner or a promise of free access.
Use synthetic data and check provider terms and quotas before making live requests.

```powershell
Set-Location 'D:\aura 2.0\aura-career-assistant'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m aura.agent --help
.\.venv\Scripts\python.exe -m aura.agent --cv '.\private\synthetic-cv.pdf' --job '.\private\synthetic-job.txt' --allow-external-processing
```

The runner reads only files you explicitly select. The model cannot choose a local
path or URL. The flag permits sending CV/job text and conversation to Gemini; omit
it to prevent agent creation. Enter `Compare my CV with this job`, then a follow-up
such as `Which requirements are not demonstrated?`. Each question makes bounded
model calls. `/reset` clears conversation checkpoints but retains the same evidence;
`/quit` closes the client and clears checkpoints. Start a new runner for different inputs.
The terminal shows your requested answers, but the service does not log document text.

The tools return original, **unverified** evidence: numbered CV pages and the pasted
posting. The graph requires both tool results before accepting an answer; this does
not prove that every generated claim is supported. The notebook-compatible pdfplumber
reader can interleave columns. Synthetic comparison tests show that the existing
PyMuPDF service preserves column order better on the tested layout; that service and
its regression tests remain unchanged. Review reading order before trusting advice.

Defaults are 6 model calls and 4 tool calls per turn, a 60-second timeout per request,
2,048 output tokens per response, and no automatic retries. Inputs are capped at the
configured PDF byte limit, 40,000 extracted CV characters, 20,000 job characters, and
4,000 question characters. Conversation length defaults to 10 successful turns. After
a failed turn, reset before retrying so an incomplete tool exchange is not resumed.
Each instance has its own UUID and in-memory checkpointer; do not share an instance
between sessions or call it concurrently. No durable history or profile verification
is implemented. LangSmith tracing stays disabled even if enabled in the shell.

Dependencies use `langchain-google-genai>=4.4.3,<4.5` to remain compatible with the
existing `google-genai` 2.x service. A future adapter/SDK upgrade requires regression
validation of both paths. No live Gemini request or factual-quality benchmark was
performed for this step; local HTTP mocks verify SDK request/response compatibility.

## Tests and code quality

These commands always select the project environment, even without activation:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -c "import app.main; from aura.core.config import Settings; print('Imports OK')"
```

Tests cover settings, profile validation, synthetic PDF text/layout extraction, error
handling, encryption, recovery, and file-size limits. Streamlit's `AppTest` exercises
navigation, explicit extraction, per-page previews, metadata, error messages, and clearing
stale previews on upload changes. Layout tests cover one, two, and three columns, spanning
section headings, multiline continuations, and exact fallback for ambiguous/merged blocks.
The UI tests also check the page-level fallback warning. All PDFs are generated in memory; personal CVs are
never used as fixtures. No external service or credentials are needed.

Gemini tests mock the SDK and use one local `httpx.MockTransport` contract test to
exercise actual SDK request serialization without contacting Google. An autouse test
guard prevents accidental live SDK clients. Tests also verify consent gating, no calls
on upload/confirmation alone, unverified states, application-owned sources, absent career
preferences, and clearing stale analysis when a document changes.

`evals/cv_extraction_baseline.json` contains four synthetic CV texts and expected results:
minimal identity, skill categories/partial dates, multiple records/mixed feature states,
and embedded instructions that must not become facts. Offline tests feed the expected
outputs as mocked responses; they validate application contracts, **not live model
accuracy**. The dataset is a starting point for later explicitly authorized prompt
evaluation, without MLflow, live API evaluation jobs, or personal CV fixtures.

Development and validation use Windows and Python 3.13.18. Python 3.12 is supported by
the metadata but has not been executed during local validation.

To format changed Python files, run `.\.venv\Scripts\python.exe -m ruff format .`.

## Prototype roadmap

The previous M0–M6 sequence has been replaced by a notebook-based Prototype 1 plan.
M0, M1.1, M1.2a, and M1.2b remain implemented foundations. P1.1 adds the modular
notebook agent and local runner; live AI validation and Streamlit chat remain pending.

| Step | Outcome | Status |
| --- | --- | --- |
| P1.1 — Notebook agent | Modular ReAct graph and tools; synthetic CV plus pasted job and follow-up | Implemented; verified offline only |
| P1.2 — Job intake | Supplied URLs, pasted fallback, and multiple-job comparison | Planned |
| P1.3 — Streamlit conversation | Upload, assessment, chat, isolated session state, and reset | Planned |
| P1.4 — Tracing and quality | LangSmith, offline tests, and a recorded synthetic AI evaluation | Planned |
| P1.5 — Cloud readiness | Community Cloud setup and hosted smoke validation | Planned |

Cover letters, application tracking, interview preparation, portfolio RAG, and automatic
job discovery are reserved for future prototypes. See [the roadmap](docs/roadmap.md)
for acceptance criteria and open decisions, and
[the architecture](docs/architecture.md) for current implementation boundaries.
The project uses the [MIT license](LICENSE).
