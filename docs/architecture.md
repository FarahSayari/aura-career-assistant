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

`aura/` is the reusable Python package. M0 introduced `core/config.py`; M1.1 adds
professional profile models under `schemas/`. These modules do not import Streamlit.
Keeping settings, schemas, and future business logic outside the
UI lets tests exercise behavior without launching a web server and allows future
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
No database, service container, API credential, or mocking framework is needed.

All installation and execution happen inside `.venv`. Local runtime downloads and
the preserved previous environment are ignored and are not project dependencies.

## Future integrations: introduce them when behavior needs them

The intended flow is approved personal evidence → verified profile → normalized job
→ explainable fit assessment → reviewed application drafts → application tracking
→ interview practice. This flow describes future work, not implemented M0 behavior.

| Component | Future responsibility | Boundary |
| --- | --- | --- |
| Pydantic models | Profile schemas implemented in M1.1; job/output schemas later | Validate data before using it |
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
