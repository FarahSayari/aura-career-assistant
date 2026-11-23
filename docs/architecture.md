# Aura 2.0 architecture

## P1.2: supplied job URLs and multiple-job evidence

P1.2 preserves the assistant/tools graph, CV reader, profile schemas, model boundary,
and current Streamlit pages. It extends job intake and tool evidence, without an
additional LLM call inside the job tool. The user has reported a successful live P1.1
manual smoke test; P1.2's multi-job reasoning is tested offline, not benchmarked live.

```text
One CV + one to five JobInput records
    -> create tools (local validation, no web request)
    -> assistant requests job_posting_tool
        -> supplied URL -> bounded public HTTP -> job text
        -> failed URL -> explicit pasted fallback, if supplied
        -> no readable source -> unavailable record + fallback message
    -> cached records with job IDs, requested/final URLs, source labels, and warnings
    -> assistant assesses readable jobs separately and compares with citations
```

`aura/schemas/job.py` defines frozen `JobInput` values: optional document label,
HTTP(S) URL, and pasted description. At least one source is required; credentials
in URLs, blank values, excessive text, and unknown fields are rejected. IDs such as
`job_1` are assigned by input order, not inferred professional facts. The legacy
`CareerAssistant(pdf_bytes, pasted_description, ...)` signature remains supported;
callers can instead supply `jobs=[JobInput(...), ...]`. Both forms together are rejected.

`aura/services/job_retrieval.py` owns networking and HTML parsing, independently of
Streamlit and Gemini. Direct retrieval was chosen for this slice to avoid another
API credential or search dependency. It accepts only supplied public HTTP(S) URLs
on standard ports. A custom HTTPX transport checks every DNS result, rejects private,
local, reserved, multicast, and supported IPv6 transition cases, and pins the socket
target to a validated IP. Original Host and TLS SNI are preserved using HTTPX's
[documented extension](https://www.python-httpx.org/advanced/extensions/#sni_hostname).
This avoids validating one DNS answer and then connecting through a second unchecked
resolution. HTTPS certificate verification stays enabled, proxies are disabled, and
redirects are explicit and rechecked; HTTPS-to-HTTP redirects are rejected.

Each retrieval owns and closes its HTTP client and response streams, performs no
automatic retries, follows at most three redirects, and accepts at most 2 MiB of
uncompressed HTML. There is a 10-second I/O timeout and a checked 30-second budget
across redirects and stream reads. DNS resolution uses the OS and is not subject to
HTTPX's timeout; this is not a hard wall-clock deadline. Job content is not logged,
saved, or sent to a retrieval provider. The job site sees the GET request and client
network address, but does not receive CV or conversation content.

The parser prefers a single schema.org `JobPosting` JSON-LD record, preserving its
description and reported metadata. It detects supported reported expiry dates without
inventing a midnight cutoff for date-only expiry. Multiple embedded postings fail as
ambiguous. Without structured data, a `main` or `article` region must have enough text
and recognizable English role-description/responsibility and qualification signals.
Menus, scripts, forms, and footer content are excluded from plain text. This is HTML
text extraction, not browser rendering, authenticity checking, or proof of completeness.

`aura/agent/tools.py` prepares CV evidence locally, then lazily retrieves jobs on the
first job-tool call. A lock protects the per-instance cache from duplicate parallel
tool calls. Each record retains `job_id`, document label, requested URL, final URL,
`source` (`job_url`, `pasted_job`, or `unavailable`), text, extraction method, and warning.
When URL access fails, provided pasted text is explicitly labeled as pasted evidence;
the requested URL is a reference, not a claim that the text was downloaded there.
Unreadable jobs retain no text. Combined evidence is capped at 40,000 characters,
each job at 20,000, and input count at five. Oversized sources are not silently cut.

`aura/prompts/career_agent_v2.py` asks for separate per-job assessments followed by
comparison, citing job IDs and CV pages, excluding unreadable jobs from ranking, and
respecting fallback warnings. The graph refuses a final assessment if no job is readable.
Facts and conclusions remain unverified. IDs and source labels reduce accidental mixing;
they do not mechanically prove every model claim is correctly attributed. Follow-ups
and resets reuse the fixed cached evidence. New or changed job inputs require a new
agent instance, avoiding stale tool results mixed with new documents.

The local runner accepts repeated `--job-url`, `--job` for a single pasted posting or
single-URL fallback, or `--jobs` for a UTF-8 JSON list of explicitly paired inputs.
The manifest is input data, not a database, model-generated path, or automatically
saved artifact. External-processing permission is required before creation; URLs are
not fetched until the job tool executes. See the README for exact commands and format.

Offline tests exercise fake DNS and HTTP responses through the real public transport,
IP pinning and TLS hostname forwarding, redirects, size/type/error handling, JSON-LD
and HTML extraction, source pairing, caching, and multi-job conversation. Real Gemini
adapter serialization is also tested with multiple jobs over local mock HTTP. A live
public Python.org posting was retrieved successfully without any CV or Gemini request.
This is a retrieval smoke test, not broad site coverage or a job recommendation.

Known limitations: JavaScript-only pages, access barriers, compressed/non-HTML responses,
unsupported language/layout patterns, and ambiguous listings can require pasted text.
No search, automatic job discovery, browser automation, persistence, Streamlit chat,
profile verification, or tracing is added here. All normal tests block live HTTP/DNS
and model clients; local `.env` files are excluded from test configuration.

## P1.1: notebook-based career agent

The [current roadmap](roadmap.md) replaces the old milestone sequence. M0–M1.2b
sections below describe preserved implementation history. P1.1 introduces a separate
core agent and local runner; Streamlit chat, formal AI evaluation, and
configured tracing are not yet implemented.

The following describes the original P1.1 boundary; P1.2 above extends job intake and
uses prompt v2. Its new job-tool payload is a collection, including for a single job.

```text
Explicit PDF bytes + one pasted job + caller permission
    -> local pdfplumber extraction and input limits
    -> CareerAssistant (one instance per conversation)
        START -> assistant (Gemini with bound tools)
                    | tool calls         ^
                    v                    |
                  ToolNode --------------+
                    |
        assistant answer without calls -> END
    -> unverified assessment; follow-ups reuse in-memory checkpoints
```

`aura/agent/graph.py` preserves the notebook's `MessagesState`, explicit assistant
node, `ToolNode`, conditional routing, and in-memory checkpointer. Two scalar state
fields count model/tool calls within the current turn. Each instance has an independent
checkpointer and UUID thread. Follow-ups append messages; reset deletes old checkpoints
and creates a new thread over the same inputs. Changed documents require a new instance.
Do not share instances across users or invoke one concurrently.

`aura/agent/tools.py` retains the notebook's two tool names. `extract_cv_text` returns
the current uploaded CV's text and page numbers; `job_posting_tool` returns the pasted
posting with its source label. Local evidence is prepared once, then returned through
the tool loop. Neither tool accepts model-generated paths, URLs, credentials, or factual
approval flags. No OpenAI call remains inside the job tool. Public URL retrieval will
be added separately in P1.2.

The PDF reader adapts the notebook's pdfplumber page loop from paths to `BytesIO`, with
size/text limits, resource cleanup, safe errors, numbered blank pages, and rejection of
encrypted or textless documents. PDF only is supported here; the notebook's DOCX/DOC
paths are not ported. The existing PyMuPDF service is unchanged. Synthetic comparison
tests preserve the same simple-page facts in both readers and demonstrate that
pdfplumber interleaves a tested two-column layout where PyMuPDF orders by column.
The agent reader is intentionally notebook-compatible, not a replacement for the
existing layout-aware service; the final active-parser decision remains open.

`aura/agent/model.py` constructs `ChatGoogleGenerativeAI` from explicit settings.
`AURA_AGENT_MODEL` selects a provisional `gemini-3.5-flash-lite` independently of the
earlier structured extractor's `AURA_GEMINI_MODEL`. The API key is shared through
`SecretStr`; no provider fallback, model discovery, or automatic retry is performed.
Ambient Google backend switches are rejected rather than silently changing backends.
The adapter is constrained to 4.4.x to preserve compatibility with the existing SDK 2.x
service. See the [official integration documentation](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai)
and [LangGraph memory documentation](https://docs.langchain.com/oss/python/langgraph/add-memory).

`aura/prompts/career_agent_v1.py` adapts the notebook's instructions for grounded
comparisons and realistic suggestions, distinguishing absent evidence from an absent
skill and reported facts from verified facts. CV/job instructions are untrusted data.
Both tools must return successfully before the graph accepts an answer. The graph
rejects unsupported tool names/arguments, invalid, empty, blocked or truncated model
responses, and excessive calls. Fresh application message IDs prevent repeated provider
IDs from replacing earlier history. These checks do not verify the truth of AI claims.

Bounds are 6 model requests by default (configurable from 2 to 12), 4 tool calls per
turn, at most 2 tool calls in one response, 60 seconds per request, 2,048 output tokens
per response, and 10 successful turns by default (configurable from 1 to 20). Inputs
have PDF byte, extracted CV, job, and question length limits. Failures produce predefined
messages without raw provider details and require reset before another request, avoiding
resumption of incomplete checkpointed tool exchanges. `close()` releases checkpoints,
the graph's evidence closures, and owned model connections. An injected test model is
not owned or closed by the service.

`python -m aura.agent` is a manual runner for this slice. The user explicitly selects
local files and grants external-processing permission; the model cannot choose files.
The runner creates a conversation but sends nothing until a question is entered. It
displays answers without writing a document store or log. Programmatic callers use
`CareerAssistant(..., consent_to_send=True)` only after obtaining user permission.
LangSmith is a framework dependency, but tracing is explicitly disabled around graph
execution, including when enabled in the environment. Privacy-aware tracing is P1.4.

Tests exercise real graph/tool execution with scripted model replies, session isolation,
memory/reset, limits, safe failures, caller permission, and parser comparisons. Real
LangChain + Gemini SDK serialization and function-result follow-ups are exercised over
local HTTP mock transports; quota-error coverage checks that no retry occurs. The test
guard blocks both SDK and adapter construction unless explicitly mocked. No personal
CV, live API, cloud deployment, or factual-quality evaluation is involved. The module
does not create or verify a `ProfessionalProfile`.

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

`aura/` is the reusable Python package. M0 introduced `core/config.py`; M1.1 adds
professional profile models under `schemas/`. These modules do not import Streamlit.
M1.2a adds a PDF parsing service under `services/`, with a separate Streamlit page in
`app/pages/cv_intelligence.py`. Keeping reusable application logic outside the UI
lets tests exercise behavior without launching a web server and allows future
interfaces to reuse the same logic.

`Settings` validates the application name and environment, loads optional credentials,
and masks the Gemini key through `SecretStr`. It resolves `.env` relative to the
project root, so configuration does not silently change with the working directory.
Constructing settings is explicit; importing a module does not load configuration,
render the page, start a server, or contact a service. The `main()` entry point reads
settings when Streamlit runs the script.

## M1.1: ProfessionalProfile data model

`aura/schemas/professional_profile.py` defines Pydantic v2 models for structured facts,
not document extraction. Import public models from `aura.schemas`, for example:

```python
from aura.schemas import ProfessionalProfile

profile = ProfessionalProfile(identity={"full_name": "Alex Example"})
serialized = profile.model_dump_json()
restored = ProfessionalProfile.model_validate_json(serialized)
assert restored == profile
```

| Root field | Record type and meaning |
| --- | --- |
| `identity` | `Identity`: optional name, title, location, and optional `ContactInformation` |
| `professional_summary` | Optional `ProfessionalSummary` with independently reviewable text |
| `technical_skills` | `SkillCategory` groups individually reviewable `Skill` entries |
| `work_experience` | `WorkExperience`: organization, role, location, dates, duties, achievements |
| `education` | `Education`: institution, degree, specialization, dates |
| `projects` | `Project`: reported/unknown status, optional features, scope, technologies, contributions, links |
| `certifications` | `Certification`: name, issuer, issue/expiry dates, credential URL |
| `awards` | `AwardAchievement`: title, description, issuer, award date, supporting URL |
| `spoken_languages` | `SpokenLanguage`: language and optional reported proficiency |
| `career_preferences` | Optional `CareerPreferences`: target roles, locations, work modes |

A partial or even empty profile is valid: unknown facts remain `None`, and collections
use independent `default_factory=list` values. An empty list means no records have been
supplied, not that the person definitely lacks that experience or skill. When a skill,
project, certification, award, language, or summary is supplied, its identifying name
or text is required. Incomplete work and education records can preserve the facts
that are available even if an organization, role, institution, or degree is missing.
Present text must be nonblank; unknown fields are rejected instead of silently dropped.

All professional records inherit `sources` and `verification_status` from
`EvidenceRecord`. Contact information and summaries are also records. Categories only
group skills; there is no root or category approval that silently verifies children.
Review of an experience/project record covers its contained text, technologies, duties,
and achievements as a unit. Separate child records, such as contact information under
identity and features under a project, keep their own review status. Per-sentence evidence
is deliberately deferred.

### Dates and development status

`PartialDate` preserves the precision actually reported:

```json
{"year": 2024}
```

```json
{"year": 2024, "month": 6}
```

```json
{"year": 2024, "month": 6, "day": 15}
```

Unspecified components remain null when serialized normally; a completely unknown
date is `None`. A supplied date requires a known year, and a day requires a month.
Calendar checks reject invalid dates, including invalid leap days. No January 1 or
month-first default is stored. `DateRange` compares only the precision known on both
sides: a clearly reversed period is rejected, while overlapping uncertain dates are
accepted. Certification expiry uses the same chronological validation.

`DateRange.is_current` defaults to `None`, not true or false. An unknown end date does
not imply present employment. An explicitly ongoing period cannot have an end date.

Project `status` supports `completed`, `in_progress`, `planned`, or `unknown`. Missing
status defaults to `unknown`; dates, achievements, and feature statuses do not infer
project completion. Planned projects cannot contain already achieved outcomes.
Completed or planned projects cannot carry an explicitly ongoing period, and an
in-progress project cannot carry an ended period. An unknown project status remains
unknown even when dates are supplied. An in-progress project may report
achievements already delivered without claiming that the entire project is complete.
Future consumers must inspect project status alongside verification: a verified plan
is still a plan, and its technologies do not establish completed experience.

The optional `features` list defaults to an independent empty list, preserving existing
project inputs. Each `ProjectFeature` has a required name, optional description, and
the same four status values (default `unknown`). An ongoing project can contain both
completed capabilities and planned additions. Features carry their own sources and
verification status (default `unverified`); neither implementation status nor parent
approval verifies a feature. Project status is not aggregated from feature statuses.

### Evidence and verification

Each lightweight `SourceReference` contains:

- `source_type`: `cv`, `portfolio`, or `manual`.
- `reference`: a document name, portfolio title, or manual-input identifier.
- Optional `locator`: a page, section, or other source location.
- Optional `url`: a validated HTTP(S) address.

Records can reference multiple sources directly, without a separate registry, database
ID, or nested document tree. A local CV filename belongs in `reference`, not in a URL.
Project links can include GitHub repository references; `github` is deliberately not
an ingestion source type. Career preferences come from the user, and any supplied
source references for preferences must be `manual`. Work modes are `remote`, `hybrid`,
and `on_site`; an empty list does not assume a preference.

Every record defaults to `unverified`, including manually entered records. Populating
fields or attaching multiple sources never promotes a record. Explicit review/import
may supply `verified` or `rejected`; a rejected entry can be retained for review but
must not be treated as a supported claim. The schema does not authenticate a reviewer
or prove that a cited document supports a claim. Future extraction must explicitly
keep extracted records unverified, even if an external payload claims to be verified.
Future drafting and matching must select approved evidence and respect rejections.

Schema validation occurs on construction and deserialization. These are ordinary
mutable Pydantic objects, not a review workflow or an immutable audit log; later edits
must be revalidated and reviewed before downstream use. Contact email/phone values and
language proficiency are preserved as nonblank reported text, without inferring a
normalized phone format, email deliverability, or a language-proficiency scale.

### Structured facts versus supporting documents

Structured records make fields, dates, unknowns, development status, and review state
explicit. CV PDFs and portfolio pages are supporting source documents, potentially
containing long narrative passages and duplicate or conflicting claims. They should
remain separate from these facts rather than being embedded as raw text in every
profile entry. This keeps the profile understandable, testable, and serializable.

Later consolidation will extract candidates from the CV PDF and the public portfolio,
associate their source locations, and propose records for user review. Claims that
describe the same fact can eventually retain both references; conflicts must remain
visible until resolved, without silently choosing a source or marking a fact verified.
Career preferences are supplied manually. GitHub repositories are not separately
ingested. These are design boundaries, not implemented parsing or merge behavior.

Qdrant is not needed to validate or represent a structured profile. There is no current
semantic search requirement, embedding pipeline, or retrieval corpus. If a later
milestone needs retrieval over longer approved source documents, Qdrant can hold that
searchable evidence while structured profile facts retain their explicit fields and
review status. M1.1 adds no ingestion, Gemini calls, UI forms, persistence, RAG, agents,
or job matching, and introduces no dependencies beyond M0.

## M1.2a: local PDF CV ingestion

```text
Streamlit CV Intelligence page
    -> uploaded PDF bytes (memory only)
    -> size/type checks + PyMuPDF extraction service
    -> numbered pages + positioned text blocks + metadata
    -> read-only page previews
```

`aura/services/pdf_extraction.py` accepts `bytes` through `extract_pdf_text`, independently
of Streamlit. It opens the stream with PyMuPDF inside a context manager, so no temporary
file is needed and the document closes on success or failure. The service does not
construct or modify a `ProfessionalProfile`. Native parser diagnostics are suppressed
while parsing, cleared from the diagnostic buffer, and restored afterward; raw parser
errors or document fragments are never logged or displayed. A lock serializes this
service's access to the process-wide native diagnostic settings.

The results are simple dataclass containers, not new professional fact models:

| Result | Contents |
| --- | --- |
| `PdfTextBlock` | Normalized text, bounding box in PDF points, original zero-based block index |
| `PdfPage` | Original one-based page number, dimensions, text blocks, page text, optional layout warning |
| `ExtractedPdf` | All pages, byte size, embedded metadata, repair flag, page count, combined text |

Every original page is retained, including blank/image-only pages. The document's
combined text uses `\f` separators to preserve page boundaries. Normalization removes
trailing whitespace, converts tabs/nonbreaking spaces, and caps runs of blank lines;
it retains line breaks, indentation, and internal spaces. Clear column layouts are
ordered using the conservative geometry strategy below. Bounding boxes and original
block indices remain available; blocks are reordered intact, never rewritten or split.
See [PyMuPDF's text extraction guidance](https://pymupdf.readthedocs.io/en/latest/recipes-text.html).

### Conservative column reading order

The original extraction uses `get_text("blocks", sort=True)`: position-sorted blocks
can put all category headings before their continuations in neighboring columns.
The refinement starts with that same extraction and changes ordering only when a
simple geometric interpretation is supported:

1. Cluster nearby left edges. Potential columns must start at least 12% of page width
   apart, which tolerates modest indentation without treating every indent as a column.
2. Require two or three supported columns, at least two text lines per active column,
   and vertical overlap between neighboring columns. Sequential sections with different
   horizontal offsets are not treated as parallel columns.
3. Require a clear gutter of at least 12 PDF points (or 2% of page width, whichever is
   greater). A block crossing a gutter can act as a spanning heading/paragraph only if
   its vertical extent is separate from all other text. Such dividers create sections;
   column ordering never moves text across them.
4. Read each section left-to-right by column, each column top-to-bottom. Keep every
   multiline block intact, so headings and continuation blocks in one column remain
   together before reading the next column.

No text labels, CV sections, skill names, or personal facts participate in detection.
For an unambiguous two-column section, `A heading, B heading, A detail, B detail`
becomes `A heading, A detail, B heading, B detail`.

Insufficient column evidence, overlapping blocks/dividers, narrow gutters, or unsupported
offsets/column counts first trigger the local-region check below. When neither method
qualifies, the **entire page** retains its exact original position-sorted order.
A second coordinate-only inspection of native text lines detects rotated text
and common cases where side-by-side lines were already merged into a single block;
those also fall back without trying to split or invent text. Normal single-column pages
keep the original order. A defaulted `PdfPage.layout_warning` field reports recognized
ambiguities, and the existing Streamlit page displays it next to that page's preview.
The extraction function signature, existing result fields, coordinates, indices,
embedded metadata, page boundaries, and parsing/error-handling behavior are preserved.

### Compact column regions on mixed-layout pages

Page-wide left-edge clustering can combine the columns in one section with right-aligned
labels elsewhere, producing too many candidates. A fixed 12-point gutter can also reject
compact, non-overlapping columns. Neither issue requires splitting intact native blocks.

When the page-wide method fails, `_local_column_order` looks for two multiline anchor
blocks that sit side-by-side and share top and bottom edges within one estimated text
line. It estimates line height from block height and reported line count, then collects
whole blocks in the resulting vertical band, allowing one extra line for unequal column
heights. The existing column confidence checks run again inside that region with a
minimum gutter of `max(2 points, estimated line height / 4)`.

Recovery requires a contiguous run in the original block order. It rejects cut/overlapping
content, close aligned continuations left outside, and competing overlapping region
interpretations. Only qualifying regions are reordered; every block's text, coordinates,
and native index remain unchanged. Other page regions retain their original order.
`layout_warning` explicitly reports local recovery rather than claiming the entire page
used the original fallback. Merged-column or rotated native blocks still force the
existing full-page fallback, without speculative line/span splitting.

This is a left-to-right heuristic for clearly separated intact blocks, not a general
layout parser. It cannot establish intended semantics for tables, recover all merged
columns, infer that a short left-aligned heading visually spans columns, or detect
every irregular layout. The conservative fallback can leave the original ordering
problem visible; it deliberately avoids confidently returning a speculative correction.

### Processing boundaries

`Settings.pdf_max_size_mb` (environment variable `AURA_PDF_MAX_SIZE_MB`) defaults to
10 MiB and must be positive. The page applies it to Streamlit's upload widget; the
service independently checks the actual byte length before opening the PDF. Bytes,
PDF identification, zero-page documents, encryption, parsing errors, and extractable
text are checked separately. All encrypted PDFs are rejected, including those that
open without a user password. Password entry and OCR are deferred.

Expected failures raise `PdfExtractionError` with a predefined user-facing explanation.
An unreadable page fails the extraction rather than silently returning a partial
success. Recoverable damage may be repaired by PyMuPDF and is flagged in the result.
A document with some textless pages returns those numbered pages with warnings in the
UI; an entirely textless document returns an error explaining the OCR limitation.

`app/pages/cv_intelligence.py` uses Streamlit's native multipage navigation and the
existing theme. Uploading does not extract text until the user clicks **Extract document
text**. It displays page count, byte-derived file size, embedded metadata, and read-only
text areas labeled by page. Errors are rendered with `st.error`, not exception dumps.
Results are rendered during the extraction run without shared caches or a persistent
result store. Changing/removing the upload clears the preview and requires another
explicit extraction. Uploaded bytes and text remain in session/process memory managed
by Streamlit; there is no disk save, external service, document logging, or database.

Ambiguous column layouts and tables may still interleave, text encodings may omit or distort
characters, and image-based pages have no text without OCR. A page with a small
selectable header over a scan can return only that header; this milestone does not
guarantee full text coverage or detect all scanned regions. Always compare previews
against the original. PDF metadata is unverified document-provided information.

M1.2b consumes these pages to propose unverified structured facts with application-owned
document references, as described below. Extracting text does not verify those facts.
Portfolio ingestion, profile verification, persistence, Qdrant/RAG, and agents remain
unimplemented.

## M1.2b: Gemini structured CV extraction

```text
In-memory ExtractedPdf
    -> explicit Google-transmission confirmation + Analyze with Gemini click
    -> gemini_extraction.extract_cv_profile (official google-genai SDK)
    -> CvExtraction JSON validation (untrusted facts only)
    -> profile_conversion.to_professional_profile (domain validation + app provenance)
    -> new ProfessionalProfile, all records unverified
    -> Streamlit JSON preview in session memory
```

### Separate factual extraction from application authority

`aura/schemas/cv_extraction.py` defines small factual models mirroring the professional
fields. It reuses safe value types (`PartialDate`, `DateRange`, `ProjectStatus`) but
does not inherit `EvidenceRecord`. It contains no verification states, source references,
career preferences, existing-profile IDs, or update operations. Unknown fields are
forbidden at every object level. Unknown dates remain partial/null and project/feature
status defaults to `unknown`.

This purposeful separation prevents model-generated approval or provenance from entering
the domain model through an accepted extraction payload. `CvExtraction.model_validate_json`
validates the raw response regardless of any SDK parsing. `profile_conversion.py` then
validates it against `ProfessionalProfile`, including project/date consistency rules,
and walks the resulting record tree to assign application-created CV references and
explicit `unverified` states, including skills, contact details, summaries, and features.
Career preferences remain absent. It creates a fresh profile and never receives an
existing verified profile to modify.

Provenance is document-level: the application supplies the uploaded filename and page
range after the response. Gemini receives neither the filename nor an opportunity to
author trusted references. Page-level attribution is explicitly unresolved rather than
inventing citations. References remain pointers to unverified evidence, not proof.

### Prompt and API boundary

`aura/prompts/cv_extraction_v1.py` contains `PROMPT_VERSION` and the system instruction.
The prompt requires explicit CV evidence, original skill categories, reported date
precision, independent project/feature status, and no duplicate experiences/projects.
All document content is untrusted data, including apparent instructions. The separate
user payload contains numbered pages and ordered text blocks with coordinates and
layout warnings. No tools, browsing, remote PDF upload, or agent workflow is enabled.

`aura/services/gemini_extraction.py` owns every external call. It uses API-key-based
Gemini Developer API access, explicitly disables Vertex/enterprise selection, and reads
`AURA_GEMINI_API_KEY`/`AURA_GEMINI_MODEL` from validated settings. The default model is
`gemini-2.5-flash`; project access must be confirmed manually. There is no model fallback
or automatic model-discovery request. The key is masked in normal representations.

Requests set JSON MIME type and `response_json_schema` from `CvExtraction`, temperature
zero, an 8,192-token output cap, a 60-second timeout, and one total SDK attempt (no retry).
The service closes its client with a context manager. It accepts only a completed
single-candidate response, then independently validates and converts the JSON. Errors
are mapped by status/type to predefined messages; response bodies, validation inputs,
API keys, and CV content are not logged or exposed through UI exceptions.

### Consent, session state, and limits

The CV page calls the service only when the confirmation checkbox is true **and** the
user clicks **Analyze with Gemini**. Upload, local extraction, confirmation alone, and
ordinary reruns do not invoke it. All extracted CV text (potentially including contact
details), block coordinates, page numbers, and layout warnings are sent to Google;
the binary PDF and embedded metadata are not. The UI explains this before confirmation.
Provider terms, data handling, and quotas still apply remotely.

Local PDF text and the preview profile live only in `st.session_state`, without shared
caches or durable storage. New uploads or explicit re-extraction clear analysis and
consent. Analysis errors preserve the local PDF preview while removing a previous
structured result, so stale success is not shown as the failed request's output.
All accepted records are labeled **Unverified**; no verification UI or save operation
is part of M1.2b.

Structural validation is not factual verification. Prompt injection, hallucinated or
omitted claims, duplication, wrong grouping, PDF extraction errors, model availability,
and output truncation remain limitations. Models may return semantically unsupported
facts in otherwise valid JSON. No live model accuracy or project access was established
by automated testing. Review every extracted fact against its source before use.

## Packaging and checks

`pyproject.toml` declares Python 3.12–3.13, runtime dependencies, development extras,
package discovery, Pytest settings, and Ruff rules. `requirements.txt` delegates to
the editable project plus its development extras rather than copying version ranges.
Only `aura` is installed as a reusable package; `app/main.py` stays the checkout's
Streamlit entry point. Run it from the repository root after installation.

`tests/test_config.py` checks configuration behavior with isolated environment variables
and temporary dotenv files. `tests/test_app.py` verifies importability and runs the
homepage through Streamlit's built-in `AppTest`. These are deterministic local checks.
`tests/test_professional_profile.py` uses only synthetic records to check partial and
complete profiles, all source/status values, independent review states and list
defaults, calendar/period validation, HTTP(S) URLs, JSON round trips, and JSON Schema
descriptions for later structured outputs. Pydantic's
[validation](https://docs.pydantic.dev/latest/concepts/validators/) and
[serialization](https://docs.pydantic.dev/latest/concepts/serialization/) APIs provide
the underlying validation and round-trip behavior.
No database, service container, or real API credential is needed for the tests.

`tests/conftest.py` generates synthetic PDFs in memory for the PDF service and Streamlit
tests. PDF tests exercise text, page boundaries and coordinates, metadata, invalid and
textless inputs, encryption, corruption/recovery, size limits, and parser cleanup.
`tests/test_pdf_reading_order.py` generates single-, two-, and three-column PDFs with
multiline continuations and spanning headings. It verifies corrected column order,
preserved blocks/coordinates/metadata, and exact fallback for sparse, overlapping,
sequential, or already-merged layouts, without personal CV fixtures.
Additional synthetic regressions cover mixed-layout pages with extra right-aligned
labels, narrow positive gutters, fragmented column continuations, preservation of the
following heading, and rejection of cut continuations or intervening content. Real PDFs
may be inspected in place with the ignored `.tools/diagnose_pdf_layout.py` utility. Its
report contains geometry and decision paths only, never CV text or embedded metadata.
Streamlit tests cover navigation, explicit extraction, numbered previews, safe errors,
and clearing stale results when the upload changes. No real CV fixture is read or saved.

`tests/test_gemini_extraction.py` uses mocked SDK responses for factual/optional fields,
partial dates, features, trust-field rejection, provenance, preferences, errors, and
JSON round trips. One real-SDK test uses a local HTTP mock transport to verify request
serialization without network access. `tests/conftest.py` blocks live SDK construction
by default. Streamlit tests mock the service and exercise the confirmation/button gate.
The synthetic gold cases in `evals/cv_extraction_baseline.json` are versioned alongside
the prompt; offline contract tests are not a measurement of actual Gemini accuracy.

All installation and execution happen inside `.venv`. Local runtime downloads and
the preserved previous environment are ignored and are not project dependencies.

## Future integrations: introduce them when behavior needs them

The intended flow is approved personal evidence → verified profile → normalized job
→ explainable fit assessment → reviewed application drafts → application tracking
→ interview practice. This flow describes future work, not implemented M0 behavior.

| Component | Future responsibility | Boundary |
| --- | --- | --- |
| Pydantic models | Profile schemas implemented in M1.1; job/output schemas later | Validate data before using it |
| Gemini API | CV extraction implemented; reasoning/drafting/interviews later | Dedicated service; explicit UI consent |
| LangGraph | P1.1 core agent implemented; Streamlit chat and later workflows planned | Explicit assistant/tools graph; isolated in-memory conversations |
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
