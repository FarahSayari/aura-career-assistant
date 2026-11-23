"""The notebook's two tools, restricted to uploaded evidence and supplied opportunities."""

import json
from collections.abc import Callable, Sequence
from io import BytesIO
from threading import Lock

import pdfplumber
from langchain_core.tools import BaseTool, tool

from aura.schemas.job import MAX_JOB_CHARACTERS, MAX_JOBS, MAX_TOTAL_JOB_CHARACTERS, JobInput
from aura.services.job_retrieval import JobRetrievalError, RetrievedJob, retrieve_job

MAX_CV_CHARACTERS = 40_000


class AgentInputError(ValueError):
    """A predefined input error safe to show without document contents."""


def read_cv_pdf(pdf_bytes: bytes, *, max_size_mb: int = 10) -> list[dict]:
    """Adapt the notebook's pdfplumber loop to memory, retaining numbered blank pages.

    This reader does not apply the existing PyMuPDF service's column corrections.
    All errors are deliberately independent of raw parser exception messages.
    """
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise AgentInputError("Provide a non-empty PDF document as bytes.")
    if max_size_mb < 1 or len(pdf_bytes) > max_size_mb * 1024 * 1024:
        raise AgentInputError("The PDF exceeds the configured size limit.")
    if not pdf_bytes.lstrip().startswith(b"%PDF-"):
        raise AgentInputError("The uploaded document must be a PDF.")
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            if pdf.doc.encryption is not None:
                raise AgentInputError("Encrypted PDFs are not supported.")
            pages = []
            character_count = 0
            for number, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                character_count += len(text)
                if character_count > MAX_CV_CHARACTERS:
                    raise AgentInputError("The CV text is too long for this prototype.")
                pages.append({"page_number": number, "text": text})
                page.close()
    except AgentInputError:
        raise
    except Exception:
        raise AgentInputError(
            "The PDF could not be read; check for damage or encryption."
        ) from None
    if not pages or not any(page["text"] for page in pages):
        raise AgentInputError("The PDF contains no extractable text. OCR is not supported.")
    return pages


def create_tools(
    cv_pdf: bytes,
    job_description: str | None = None,
    *,
    jobs: Sequence[JobInput] | None = None,
    max_size_mb: int = 10,
    job_retriever: Callable[[str], RetrievedJob] | None = None,
) -> list[BaseTool]:
    """Prepare local evidence once; tools never accept model-generated filesystem paths.

    No URL is fetched on construction. The job tool fetches once on its first call
    and retains separate source records for this conversation. Nothing is written.
    """
    if job_description is not None and jobs is not None:
        raise AgentInputError("Supply a job description or a jobs collection, not both.")
    if jobs is None:
        if not isinstance(job_description, str) or not job_description.strip():
            raise AgentInputError("Provide a non-empty pasted job description or jobs collection.")
        if len(job_description) > MAX_JOB_CHARACTERS:
            raise AgentInputError("The pasted job description is too long for this prototype.")
        jobs = [JobInput(description=job_description)]
    if not 1 <= len(jobs) <= MAX_JOBS or not all(isinstance(job, JobInput) for job in jobs):
        raise AgentInputError(f"Supply between one and {MAX_JOBS} validated JobInput records.")
    inputs = tuple(jobs)
    urls = [str(job.url).split("#", 1)[0] for job in inputs if job.url is not None]
    if len(urls) != len(set(urls)):
        raise AgentInputError("Duplicate job URLs were supplied; keep each opportunity once.")
    if sum(len(job.description or "") for job in inputs) > MAX_TOTAL_JOB_CHARACTERS:
        raise AgentInputError("Combined pasted job descriptions exceed the 40,000-character limit.")
    pages = read_cv_pdf(cv_pdf, max_size_mb=max_size_mb)
    fetch = job_retriever or retrieve_job
    job_cache = None
    job_lock = Lock()

    def collect_jobs() -> list[dict]:
        evidence = []
        total = 0
        for number, job in enumerate(inputs, start=1):
            record = {
                "job_id": f"job_{number}",
                "label": job.label or f"Job {number}",
                "requested_url": str(job.url) if job.url else None,
                "final_url": None,
                "source": "unavailable",
                "text": None,
                "extraction_method": None,
                "warning": None,
            }
            if job.url is not None:
                try:
                    result = fetch(str(job.url))
                    record.update(
                        source="job_url",
                        text=result.text,
                        final_url=result.final_url,
                        extraction_method=result.extraction_method,
                    )
                except JobRetrievalError as error:
                    record["warning"] = str(error)
                except Exception:
                    record["warning"] = (
                        "The posting could not be read. Paste the description instead."
                    )
            if record["text"] is None and job.description is not None:
                record.update(source="pasted_job", text=job.description)
                if job.url is not None:
                    record["warning"] = (record["warning"] or "No usable URL text.") + (
                        " Using user-pasted fallback; it was not retrieved from the URL."
                    )
            text = record["text"] or ""
            if len(text) > MAX_JOB_CHARACTERS or total + len(text) > MAX_TOTAL_JOB_CHARACTERS:
                record.update(
                    source="unavailable",
                    text=None,
                    final_url=None,
                    warning=(
                        "Job text exceeds the per-job or combined limit. "
                        "Supply shorter pasted text."
                    ),
                )
            else:
                total += len(text)
            evidence.append(record)
        return evidence

    @tool
    def extract_cv_text() -> str:
        """Read the current uploaded CV, returning unverified text with page numbers.

        No arguments are needed: the application supplies this session's document.
        """
        return json.dumps(
            {
                "source": "uploaded_cv",
                "pages": pages,
                "layout_warning": "pdfplumber reading order may interleave columns; no OCR.",
            },
            ensure_ascii=False,
        )

    @tool
    def job_posting_tool() -> str:
        """Read all supplied jobs with separate IDs, URLs, text, and retrieval/fallback status.

        Only application-supplied URLs are fetched. No search, discovery, or arguments.
        Unavailable jobs have no evidence and cannot be assessed or ranked.
        """
        nonlocal job_cache
        with job_lock:
            if job_cache is None:
                job_cache = collect_jobs()
        return json.dumps({"source": "provided_jobs", "jobs": job_cache}, ensure_ascii=False)

    return [extract_cv_text, job_posting_tool]
