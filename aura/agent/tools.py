"""The notebook's two tools, restricted to one uploaded PDF and one pasted job."""

import json
from io import BytesIO

import pdfplumber
from langchain_core.tools import BaseTool, tool

MAX_CV_CHARACTERS = 40_000
MAX_JOB_CHARACTERS = 20_000


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


def create_tools(cv_pdf: bytes, job_description: str, *, max_size_mb: int = 10) -> list[BaseTool]:
    """Prepare local evidence once; tools never accept model-generated filesystem paths.

    No network call, file write, LLM summary, or verification is performed here.
    """
    if not isinstance(job_description, str) or not job_description.strip():
        raise AgentInputError("Provide one non-empty pasted job description.")
    if len(job_description) > MAX_JOB_CHARACTERS:
        raise AgentInputError("The pasted job description is too long for this prototype.")
    pages = read_cv_pdf(cv_pdf, max_size_mb=max_size_mb)

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
        """Read the current pasted job description, returning its unverified source text.

        No URL retrieval or web search is available in this first implementation step.
        """
        return json.dumps({"source": "pasted_job", "text": job_description.strip()})

    return [extract_cv_text, job_posting_tool]
