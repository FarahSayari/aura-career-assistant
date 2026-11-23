"""Synthetic PDF evidence only; no personal document fixtures or external requests."""

import json

import pymupdf
import pytest

from aura.agent.tools import AgentInputError, create_tools, read_cv_pdf
from aura.schemas.job import JobInput
from aura.services.job_retrieval import JobRetrievalError, RetrievedJob
from aura.services.pdf_extraction import extract_pdf_text


def test_notebook_tools_preserve_evidence_and_page_boundaries(make_pdf):
    tools = create_tools(
        make_pdf(["Alex Example\nPython developer", "", "Built synthetic test suites"]),
        "Requires Python. SQL is preferred.",
    )
    cv, job = [json.loads(tool.invoke({})) for tool in tools]

    assert [tool.name for tool in tools] == ["extract_cv_text", "job_posting_tool"]
    assert [page["page_number"] for page in cv["pages"]] == [1, 2, 3]
    assert cv["pages"][1]["text"] == ""
    assert "Python developer" in cv["pages"][0]["text"]
    assert cv["source"] == "uploaded_cv"
    assert "interleave columns" in cv["layout_warning"]
    assert job["source"] == "provided_jobs"
    assert job["jobs"][0]["source"] == "pasted_job"
    assert job["jobs"][0]["text"] == "Requires Python. SQL is preferred."
    assert job["jobs"][0]["job_id"] == "job_1"
    assert all(tool.args == {} for tool in tools)  # No model-selected paths or URLs.


@pytest.mark.parametrize("value", [b"", b"not a PDF", b"%PDF-1.7\ncorrupted", None])
def test_invalid_documents_have_safe_errors(value, caplog):
    with pytest.raises(AgentInputError):
        read_cv_pdf(value)
    assert "corrupted" not in caplog.text


def test_textless_pdf_rejected(make_pdf):
    with pytest.raises(AgentInputError, match="OCR"):
        read_cv_pdf(make_pdf([""]))


def test_encrypted_pdf_rejected_even_with_empty_user_password():
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "Synthetic encrypted CV")
        data = pdf.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="synthetic-owner", user_pw=""
        )
    with pytest.raises(AgentInputError, match="Encrypted"):
        read_cv_pdf(data)


def test_size_limit_before_parsing():
    with pytest.raises(AgentInputError, match="size limit"):
        read_cv_pdf(b"%PDF-" + b"x" * (1024 * 1024), max_size_mb=1)


@pytest.mark.parametrize("job", ["", "   ", "x" * 20_001, None])
def test_invalid_job_descriptions_rejected_before_document_parsing(make_pdf, job):
    with pytest.raises(AgentInputError, match="job description"):
        create_tools(make_pdf(["Synthetic CV"]), job)


def test_cv_character_limit(make_pdf):
    # Many short lines on separate pages, not long lines clipped off a PDF page.
    data = make_pdf([("Synthetic text " * 5 + "\n") * 20] * 30)
    with pytest.raises(AgentInputError, match="too long"):
        read_cv_pdf(data)


def test_parser_comparison_single_column_preserves_same_facts(make_pdf):
    data = make_pdf(["Alex Example\nPython and SQL", "Synthetic project"])
    notebook_pages = read_cv_pdf(data)
    existing_pages = extract_pdf_text(data).pages

    assert len(notebook_pages) == len(existing_pages) == 2
    for notebook, existing in zip(notebook_pages, existing_pages, strict=True):
        assert notebook["text"].split() == existing.text.split()


def test_parser_comparison_documents_column_order_difference():
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=650)
        for x, y, text in [
            (50, 90, "Category A"),
            (50, 160, "A first detail\nA continuation"),
            (350, 100, "Category B"),
            (350, 170, "B first detail\nB continuation"),
        ]:
            page.insert_text((x, y), text)
        data = pdf.tobytes()

    notebook = read_cv_pdf(data)[0]["text"]
    existing = extract_pdf_text(data).text
    assert notebook.index("Category B") < notebook.index("A first detail")
    assert existing.index("A first detail") < existing.index("Category B")
    assert sorted(notebook.split()) == sorted(existing.split())


def test_multiple_sources_are_lazy_cached_and_keep_distinct_ids(make_pdf):
    calls = []

    def fetch(url):
        calls.append(url)
        return RetrievedJob(
            "Python required; SQL preferred.",
            "https://jobs.example.test/final",
            "json_ld_job_posting",
        )

    jobs = [
        JobInput(label="Developer", url="https://jobs.example.test/python"),
        JobInput(label="Analyst", description="SQL required; Python preferred."),
    ]
    tool = create_tools(make_pdf(["Synthetic Python CV"]), jobs=jobs, job_retriever=fetch)[1]
    assert calls == []
    first = json.loads(tool.invoke({}))["jobs"]
    assert json.loads(tool.invoke({}))["jobs"] == first
    assert calls == ["https://jobs.example.test/python"]
    assert [job["job_id"] for job in first] == ["job_1", "job_2"]
    assert first[0]["source"] == "job_url"
    assert first[0]["requested_url"] == "https://jobs.example.test/python"
    assert first[0]["final_url"] == "https://jobs.example.test/final"
    assert first[1]["source"] == "pasted_job" and first[1]["requested_url"] is None
    assert first[0]["text"] != first[1]["text"]


def test_failed_url_fallback_is_pasted_evidence_not_web_evidence(make_pdf):
    def fetch(_):
        raise JobRetrievalError("The website denied access. Paste the job description instead.")

    jobs = [JobInput(url="https://jobs.example.test/a", description="Python required")]
    tool = create_tools(make_pdf(["CV"]), jobs=jobs, job_retriever=fetch)[1]
    job = json.loads(tool.invoke({}))["jobs"][0]
    assert job["source"] == "pasted_job" and job["text"] == "Python required"
    assert job["requested_url"] and job["final_url"] is None
    assert "not retrieved from the URL" in job["warning"]


def test_unavailable_jobs_have_no_text_and_do_not_hide_usable_jobs(make_pdf):
    def fetch(_):
        raise RuntimeError("SYNTHETIC_PRIVATE_ERROR")

    tool = create_tools(
        make_pdf(["CV"]),
        jobs=[JobInput(url="https://jobs.example.test/a"), JobInput(description="SQL required")],
        job_retriever=fetch,
    )[1]
    jobs = json.loads(tool.invoke({}))["jobs"]
    assert jobs[0]["source"] == "unavailable" and jobs[0]["text"] is None
    assert "PRIVATE_ERROR" not in jobs[0]["warning"]
    assert jobs[1]["text"] == "SQL required"


@pytest.mark.parametrize(
    "jobs",
    [
        [],
        [JobInput(description="Job")] * 6,
        [
            JobInput(url="https://jobs.example.test/a#x"),
            JobInput(url="https://jobs.example.test/a#y"),
        ],
        [JobInput(description="x" * 15_000)] * 3,
    ],
)
def test_invalid_job_collections_rejected_before_model_calls(make_pdf, jobs):
    with pytest.raises(AgentInputError):
        create_tools(make_pdf(["CV"]), jobs=jobs)


def test_legacy_description_cannot_be_combined_with_jobs(make_pdf):
    with pytest.raises(AgentInputError, match="not both"):
        create_tools(make_pdf(["CV"]), "Job", jobs=[JobInput(description="Other")])


def test_total_retrieved_text_limit_does_not_silently_truncate(make_pdf):
    def fetch(url):
        return RetrievedJob("x" * 15_000, url, "json_ld_job_posting")

    tool = create_tools(
        make_pdf(["CV"]),
        jobs=[JobInput(url=f"https://jobs.example.test/{n}") for n in range(3)],
        job_retriever=fetch,
    )[1]
    jobs = json.loads(tool.invoke({}))["jobs"]
    assert [len(job["text"] or "") for job in jobs] == [15_000, 15_000, 0]
    assert jobs[2]["source"] == "unavailable" and "limit" in jobs[2]["warning"]
