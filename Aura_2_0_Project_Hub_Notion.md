# ✨ Aura 2.0 — Agentic AI Career Assistant

> **Project hub · Planning reference · Version 0.1 · 8 November 2026**  
> **Status:** Planned — development not yet started  
> **Project type:** Personal, single-user AI engineering project  
> **Core objective:** Help me evaluate job opportunities, prepare truthful tailored applications, track applications, identify skill gaps, and practice interviews.  
> **Primary role focus:** AI Engineer (and relevant early-career AI positions)

---

## 🧭 1. Product vision and boundaries

**From job description to confident application and interview preparation.** Aura remembers my verified professional background and helps me through the job-search journey, while keeping me in control of all external actions.

**V1 principle:** Start with a pasted job description (and optionally a URL when accessible). **Automatic job discovery comes later** and must not block core functionality.

**Non-goals for the initial version:** Multi-user recruiting platform, training a custom LLM, automatic submission of applications, scraping sites against their rules, or a heavyweight production infrastructure stack.

**Success looks like:** I can provide a job posting, receive an explainable fit assessment and evidence-backed skill gaps, generate a tailored letter and email, save the opportunity, update its status, and launch role-specific interview practice.

---

## 🧩 2. Methodology, approaches, tools, and technologies

> **Remember:** A methodology organizes how we work; an engineering approach defines practices we adopt; a framework helps us build functionality; a tool performs specific tasks. Using a tool alone does not automatically mean we're following an approach.

| Area | Name | Category | Purpose in Aura | Adoption |
| --- | --- | --- | --- | --- |
| Project management | **Scrumban** | Methodology / workflow | Organize backlog, short iterations, limited work in progress and reviews | **From day one** |
| AI engineering lifecycle | **GenAIOps** | Engineering practices / approach | Version and evaluate prompts, RAG, and agents; trace failures; monitor quality after changes | **From day one, progressively** |
| Software delivery | **DevOps / CI/CD** | Engineering practices | Build, test and package software reproducibly | **From foundation** |
| Application language | **Python** | Programming language | Implement AI logic, tools, integrations and application logic | **Chosen** |
| User interface | **Streamlit** | UI framework | Provide interactive personal dashboard and workflows | **Chosen** |
| LLM | **Google Gemini API** | Hosted model/service | Extraction, reasoning, drafting and interview feedback; avoids heavy local inference | **Chosen initially** |
| Agent orchestration | **LangGraph** | Agent framework | Coordinate steps, nodes, state, tool calls and approval gates | **Chosen; introduce when needed** |
| Knowledge retrieval | **Qdrant** | Vector database | Store embeddings of approved professional content and retrieve evidence semantically | **Chosen; introduce for RAG** |
| Semantic representation | **Embedding model** | Model/component | Encode documents and queries for Qdrant; provider/model to be decided | **To decide** |
| Prompt experiments | **MLflow** | Experiment/evaluation platform | Record prompt versions, configs, datasets and comparison results; can also trace GenAI | **Planned for AI experiments** |
| Agent observability | **LangSmith** | Tracing/evaluation platform | Inspect LangGraph runs, tool calls, failures, latency and evaluation cases | **Planned for agent milestone** |
| Automated test writing | **Pytest** | Testing framework | Implement unit, integration and evaluation-related tests | **From foundation** |
| CI automation | **GitHub Actions** | Automation service | Run configured checks on pushes/PRs; does not write tests or guarantee LLM correctness | **From foundation** |
| Version control | **Git + GitHub** | Source control | Manage changes, branches, issues and repository | **From foundation** |
| Work tracking | **GitHub Projects / Issues** | Project tool | Maintain Scrumban board and milestone tasks | **From foundation** |
| Data validation | **Pydantic** | Python library | Define and validate structured LLM outputs, profile and job schemas | **From first AI feature** |
| Persistent application state | **SQLite initially** | Relational database | Store jobs, statuses, dates, notes, generated document references and interview sessions | **Recommended for V1** |
| Database growth option | **PostgreSQL** | Relational database | Replace SQLite only if deployment/concurrency warrants it | **Optional later** |
| Environment packaging | **Docker** | Container tooling | Make app + services easier to reproduce/deploy | **After working local slice** |
| Formatting/linting | **Ruff** | Code-quality tool | Check style and simple code issues | **Recommended from foundation** |
| Secret handling | **Environment variables / local secrets** | Security practice | Keep API keys, personal documents and credentials out of Git | **Mandatory** |
| Web/job-source integration | **Approved APIs, permitted feeds, accessible pages, job-alert emails** | Data connectors | Discover vacancies without relying on prohibited scraping | **Later milestone** |
| Company/interview research | **Permitted web search + source references** | Retrieval capability | Find public interview experiences, differentiate sourced reports from generated practice questions | **Later milestone** |
| Large-scale orchestration | **Kubernetes** | Infrastructure platform | Coordinate containers across machines; unnecessary for a solo local V1 | **Not planned** |

### The tools in one sentence

**Scrumban** organizes tasks → **Python + Streamlit** deliver the application → **Gemini** generates and reasons → **LangGraph** coordinates agents → **Qdrant** retrieves professional evidence → **MLflow** compares experiments → **LangSmith** traces agent execution → **Pytest** defines tests → **GitHub Actions** runs selected checks → **GenAIOps** is the set of quality practices tying this together.

**Important boundaries:** MLflow and LangSmith overlap; use each for a clear learning goal rather than duplicating every trace. RAG is useful for detailed documents, but small structured facts (career preferences, verified skills, application status) should remain structured data, not only vectors. LLM evaluation checks are probabilistic; passing tests does not prove every future answer will be perfect.

---

## 📥 3. Exact inputs

### A. Persistent personal sources (set up once; update when needed)

| Input | Examples | What Aura uses it for | Storage/handling |
| --- | --- | --- | --- |
| **CV** | PDF and extracted education, skills, experience | Build verified professional profile | Private file + structured profile |
| **GitHub profile** | Public repository links, READMEs, selected project descriptions | Evidence of projects and technologies | Selected indexed documents + links; avoid unsupported skill inferences |
| **Portfolio** | Public project pages and explanations | Deep project details for tailored responses | Selected indexed pages + source links |
| **Career preferences** | AI Engineer roles, junior level, location/remote preferences, constraints | Filter and interpret opportunities | Editable structured settings |
| **Cover letter template** | Preferred introduction, body and closing structure | Constrain tailored letter generation | Editable versioned template |

**Recommended optional additions:** Verified certification details, preferred application email style, achievements not documented in CV, and a personal “do not claim” list. All require user review.

### B. Per-job and per-task inputs

| Input | When used |
| --- | --- |
| **Job description text** | Required for first job-analysis workflow; pasted manually in V1 |
| **Job URL** | Optional; fetch only where allowed and technically accessible; paste text as fallback |
| **Company, role, location, source, application deadline** | Extract if available, otherwise edit manually |
| **User commands and choices** | Generate letter/email, accept/reject suggested edits, save application, start interview |
| **Interview responses / optional code solutions** | Mock-interview feedback and coding exercises |

### C. Development and evaluation data (NOT model training data)

- Start with **15–20 representative job descriptions** relevant to target roles; label fit and important criteria manually for initial evaluation.
- Build a small set of **expected profile-extraction and letter-grounding test cases**; include synthetic CVs only to test robustness across formats, not to personalize Aura to other users.
- Keep evaluation fixtures separate from real application data and private documents.
- **We are not fine-tuning Gemini.** CV/portfolio are knowledge sources; evaluation examples are tests.

---

## 📤 4. Exact outputs

| Output | What the user sees | Key guardrail |
| --- | --- | --- |
| **1. Job-fit assessment** | Strong / moderate / weak fit, with requirement-by-requirement justification | No arbitrary “AI confidence percentage” disguised as objective truth |
| **2. Skill-gap report** | Demonstrated strengths, genuine gaps and **not enough evidence** areas | Missing from CV ≠ definitely missing from skill set |
| **3. Improvement recommendations** | CV emphasis, project highlights and prioritized learning suggestions | Never invent skills or work experience |
| **4. Tailored cover letter** | Editable letter following the saved personal template | Ground every factual claim in approved profile evidence |
| **5. Application email draft** | Editable subject + message for applying | User sends/approves; no automatic sending in V1 |
| **6. Application tracker** | Saved opportunities, dates, notes, status and relevant drafts | Clear distinction between saved, drafted and actually submitted |
| **7. Interview preparation** | HR + technical questions, role-based suggested responses, mock sessions and feedback | Generated questions are not presented as confirmed company questions |
| **8. Duplicate warning** | Alert for previously saved/applied-to similar opportunity | Permit correction when postings differ |
| **9. Career insights** | Common required skills and recurring gaps across collected jobs | Explain sample size; insights are not a forecast of hiring outcomes |

**Application statuses:** Saved → Preparing → Applied → Interview → Offer / Rejected / Withdrawn. Status can be edited manually; a generated email does **not** mean an application was submitted.

**Interview module:** Start with generated HR/technical Q&A; add interactive mock interview and evaluation; later add cited company-specific research and optional Python/SQL coding practice. Do not execute arbitrary submitted code without safe isolation.

---

## 🏗️ 5. Logical modules and flow

| Module | Responsibilities | Main implementation pattern | Depends on |
| --- | --- | --- | --- |
| **M1. Profile & knowledge** | Import CV, connect selected portfolio/GitHub evidence, extract and verify skills, manage preferences/templates | Document parsers, Pydantic, structured store; Qdrant when needed | Foundation |
| **M2. Job intake & parsing** | Paste job / optional URL, extract company/requirements, normalize and save | Streamlit, Gemini structured output, validation | M1 |
| **M3. Job matching & gap analysis** | Compare requirements with verified evidence and preferences, explain fit | Deterministic criteria + LLM-supported explanations + retrieval | M1–M2 |
| **M4. Application drafting** | Tailor CV advice, generate cover letter/email, keep editable versions | Gemini, templates, evidence checks, approval UI | M1–M3 |
| **M5. Application tracker** | Persist status/history, duplicates, notes and drafts | SQLite, Python services, Streamlit | M2 |
| **M6. Interview coach** | HR/technical questions, mock interview, feedback, practice progress | Gemini, structured rubrics, saved sessions | M1–M5 |
| **M7. Job discovery (later)** | Search supported sources, ingest listings, dedupe, rank | Source-specific permitted connectors | M2–M5 |
| **M8. Career insights (later)** | Aggregate skill demands, gaps and application activity | SQL / Python analytics | M3, M5 |
| **Cross-cutting quality** | Evaluation, tracing, tests, versioning, privacy | Pytest, GitHub Actions, MLflow, LangSmith, GenAIOps practices | All |

**High-level path:** Personal sources → Verified profile + searchable evidence; job description → normalized job → fit/gap analysis → letter/email drafts → saved application → interview practice. Future discovery feeds jobs into the **same** job-intake module.

**Architecture rule:** Use plain Python and database operations for predictable tasks (CRUD, statuses, duplicate checks). Use Gemini for language understanding/generation and LangGraph only for workflows that need stateful coordination, tool use or review gates. A multi-agent system is **not** mandatory for V1.

---

## 🗺️ 6. Roadmap — milestones, not a fixed deadline

> **Planning estimate:** Seven short milestones over approximately **6–10 part-time weeks**, depending on learning, testing and available time. These are estimates, not commitments; deliver one useful vertical slice first. **All tasks currently unchecked.**

### M0 — Foundation (roughly 3–5 working sessions)

- [ ] Create repository, README, development environment and `.gitignore` for private data/secrets
- [ ] Define structure (`app/`, `services/`, `tests/`, `evals/`, `docs/`)
- [ ] Initialize Python, Streamlit, Gemini configuration, Pydantic, Pytest and Ruff
- [ ] Add a minimal GitHub Actions workflow for lint + unit tests
- [ ] Create GitHub Project board: **Backlog · To Do · In Progress · Review · Done**

**Done when:** Streamlit opens locally; a minimal Gemini call works via secret configuration; CI runs basic tests.

### M1 — Personal profile (roughly 1 week)

- [ ] Import your CV and extract a **structured `ProfessionalProfile`**
- [ ] Review, edit and approve extracted facts before they become trusted
- [ ] Add career preferences and cover-letter template
- [ ] Add selected portfolio and GitHub evidence; source attribution
- [ ] Decide which facts stay structured and which documents merit Qdrant indexing
- [ ] Write baseline profile-extraction cases; track prompt comparison in MLflow

**Done when:** Aura can show an accurate, editable profile and cite source evidence.

### M2 — First working job-fit slice (roughly 1 week) ⭐

- [ ] Paste a job description and parse requirements into a validated `JobPosting`
- [ ] Compare job requirements with verified profile and preferences
- [ ] Show **strong / moderate / weak** fit with evidence and unknowns
- [ ] Generate actionable skill-gap analysis
- [ ] Create a small manually labeled evaluation set (initial goal: 15–20 jobs)

**Done when:** A job can be pasted, analyzed and meaningfully evaluated end to end. **First usable product milestone.**

### M3 — Tailored applications (roughly 1 week)

- [ ] Generate editable cover letter using saved structure
- [ ] Generate editable application email (subject + body)
- [ ] Recommend truthful CV adjustments without fabricating qualifications
- [ ] Add user review/approval for exported content
- [ ] Evaluate grounding, completeness, template adherence and unsupported claims

**Done when:** An analyzed job can produce reviewed application drafts backed by known facts.

### M4 — Application tracking (roughly 1 week)

- [ ] Create local SQLite schema for jobs, applications, statuses, notes and draft versions
- [ ] Save/update opportunities and mark actual submission dates manually
- [ ] Add duplicate warnings and filters
- [ ] Add a Streamlit tracker and application detail view

**Done when:** You can answer “Where did I apply?” without external spreadsheets.

### M5 — Interview preparation (roughly 1–2 weeks)

- [ ] Generate HR + role-specific technical questions for a saved job
- [ ] Draft sample answers grounded in your real projects
- [ ] Add mock Q&A sessions and structured feedback on correctness/clarity
- [ ] Save interview sessions and improvement areas
- [ ] Trace multi-step orchestration with LangSmith if LangGraph is introduced

**Done when:** A tracked job can launch a tailored practice interview with actionable feedback.

### M6 — Reliability & packaging (roughly 3–5 working sessions)

- [ ] Build regression evaluations for extraction, matching, drafting, agent tasks and RAG as used
- [ ] Version prompts/configs and record results with MLflow
- [ ] Run inexpensive deterministic checks on every push with GitHub Actions
- [ ] Run API-dependent LLM evaluations selectively or manually to control cost/quota
- [ ] Confirm no CVs, API keys or sensitive logs are committed; review tracing redaction
- [ ] Add Docker setup if it improves repeatability
- [ ] Write architecture and limitations documentation; capture representative screenshots

**Done when:** The personal V1 is repeatable, tested, documented and safe enough for daily use.

### After V1 — Optional expansion, ordered by value

- [ ] **Job discovery connectors** for permitted sources (including LinkedIn alerts; investigate Tanitjobs options); maintain URL/paste fallback
- [ ] **Company-specific interview research** with links, publication context and clear sourced-vs-generated labels
- [ ] **Career insights dashboard** across accumulated postings and outcomes
- [ ] **Coding interview practice** with safely isolated execution or non-executing review
- [ ] Consider PostgreSQL/deployment only when actual requirements justify it

---

## ✅ 7. Development status dashboard

| Milestone | Status | Evidence of completion | Next action |
| --- | --- | --- | --- |
| M0 Foundation | ⬜ Not started | Working local app + CI | Initialize repository |
| M1 Profile | ⬜ Not started | Approved profile + sources | Define `ProfessionalProfile` schema |
| M2 Job fit | ⬜ Not started | Explainable analysis of pasted job | Define `JobPosting` + fit criteria |
| M3 Drafting | ⬜ Not started | Reviewed letter + email | Capture cover letter template |
| M4 Tracking | ⬜ Not started | Saved application history | Define database entities |
| M5 Interview | ⬜ Not started | Tailored practice interview | Define question/feedback schema |
| M6 Reliability | ⬜ Not started | Quality checks + documentation | Build evaluation baseline |
| Future discovery | 🕒 Backlog | At least one compliant live source | Review access options after V1 |

**Current focus:** M0 → first task: initialize repo and agree on the `ProfessionalProfile` and `JobPosting` schemas before adding complex agent logic.

### Weekly Scrumban review template

**Week / dates:** …  
**Completed:** …  
**Test/evaluation results:** …  
**Blocked by:** …  
**Next 1–2 priorities:** …  
**Architecture/experiment decisions:** …

### Definition of Done (for each feature)

- [ ] Acceptance criteria met and user flow works
- [ ] Unit/integration tests pass where appropriate
- [ ] Structured LLM results validated; failures handled
- [ ] Relevant AI evaluation examples reviewed
- [ ] Factual claims traceable to approved sources
- [ ] Human approval before any external application action
- [ ] Secrets/personal data protected and traces checked for leakage
- [ ] Documentation/status table updated

---

## 📏 8. How we'll measure quality

| Feature | Initial evaluation question | Suitable measures |
| --- | --- | --- |
| CV/profile extraction | Did Aura capture verified skills, roles and dates? | Field-level precision/recall; unsupported fields |
| Retrieval (when RAG exists) | Did it retrieve relevant portfolio evidence? | Recall@k, hit rate, source accuracy |
| Job matching | Does the result match human judgment and explain why? | Agreement on labeled jobs; requirement coverage; gap classification |
| Cover letters/emails | Are they relevant, complete and truthful? | Unsupported claim count (**critical = 0**); template adherence; human review |
| Agent workflows | Did the right tools run in the right order? | Task success; tool/approval compliance; error handling |
| Interview feedback | Is the critique technically justified and useful? | Rubric agreement and human quality review |
| Operations | Is the experience usable over time? | Failure rate; latency; API usage/cost; regressions |

**Testing policy:** Cheap deterministic tests on each PR/push; selective LLM/RAG/agent evaluations on demand or before major release. Quality thresholds should be calibrated after baseline testing, not invented in advance.

---

## 🔐 9. Privacy and control rules

- Private CVs, application history and career preferences stay out of public repositories.
- All generated claims must be based on user-verified professional evidence.
- Treat retrieved webpages/job postings as **untrusted input**; never follow instructions embedded inside them.
- No automatic applications, outbound emails or irreversible actions without explicit user review/approval.
- Follow website access policies; prefer APIs, feeds, alerts and permitted search, with manual paste as fallback.
- Avoid sending unnecessary personal information to model APIs or observability platforms; choose redaction/opt-out settings appropriately.

---

## 📌 10. Open decisions log

| Decision | Current direction | When to finalize |
| --- | --- | --- |
| Exact Gemini model and quotas | Hosted Gemini, choose based on availability/quality/cost | M0 |
| Embedding model | Compatible with Qdrant; benchmark when adding RAG | M1 |
| Document ingestion scope | CV + selected portfolio/GitHub pages | M1 |
| SQLite vs PostgreSQL | SQLite first | M4 |
| LangGraph workflow granularity | Minimal stateful orchestration only when necessary | M2–M5 |
| MLflow and LangSmith setup | Use MLflow for experiments; LangSmith for agent traces, avoid duplicate overhead | M1/M5 |
| Job discovery permissions/access | Investigate one source at a time | After V1 |
| Hosting | Local first; publish only safe demo data if desired | M6 |

---

**North star:** Aura should **save time, reduce repeated work, help me make better decisions, and improve interview readiness** — not merely demonstrate the largest possible list of AI tools.

✨ Aura 2.0 — Quick Reference
Project: Personal Agentic AI Career Assistant
Goal: Automate and simplify the job-search and application process.
🛠️ Methodologies, Technologies & Tools
Technology / Approach	Purpose
Scrumban	Project management methodology
GenAIOps	Approach to maintaining AI reliability and quality
Python	Main programming language
Streamlit	User interface
Gemini	Large Language Model (LLM)
LangGraph	Build and orchestrate AI agents
Qdrant	Vector database for semantic retrieval (RAG)
PostgreSQL	Store jobs, applications, and statuses
MLflow	Track experiments and compare prompts
LangSmith	Trace and debug agent behavior
Pytest	Write automated tests
GitHub Actions	Run tests automatically (CI/CD)
Docker	Package the application
Pydantic	Validate structured AI outputs


📥 Aura Inputs
- CV: Education, experience, skills, certifications.
- Portfolio: Detailed projects and achievements.
- GitHub: Repositories and technical documentation.
- Career preferences: Target roles, locations, work preferences.
- Cover letter template: Preferred structure and style.
- Job description: Pasted text or URL when supported.
📤 Aura Expected Outputs
1. Job Matching: Strong, moderate, or weak compatibility.
2. Skill-Gap Analysis: Matching skills and missing requirements.
3. CV Improvements: Personalized recommendations.
4. Cover Letter: Tailored to the position.
5. Application Email: Professional email generation.
6. Application Tracking: Companies, dates, statuses, and history.
7. Interview Preparation: HR questions, technical questions, mock interviews.
8. Career Insights: Recurring skill gaps and learning recommendations.
🚀 Future Features
- Automatic job discovery (LinkedIn, Tanitjobs, etc.).
- Company-specific interview research.
- Automated portfolio/GitHub synchronization.
🧠 Key Concepts to Remember
Scrumban → Organizes our work.

GenAIOps → Helps maintain AI quality and reliability.

LangGraph → Builds the agent workflows.

Gemini → Provides LLM intelligence.

Qdrant → Retrieves relevant professional knowledge.

PostgreSQL → Remembers job applications.

MLflow → Compares AI experiments.

LangSmith → Shows what happens inside the agents.

GitHub Actions → Automates tests and CI/CD.

Our development strategy: Build incrementally, starting with professional profile extraction and job matching, then application generation, tracking, and interview preparation.