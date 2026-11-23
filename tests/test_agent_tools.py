"""Synthetic PDF evidence only; no personal document fixtures or external requests."""

import json

import pymupdf
import pytest

from aura.agent.tools import AgentInputError, create_tools, read_cv_pdf
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
    assert job == {"source": "pasted_job", "text": "Requires Python. SQL is preferred."}
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
