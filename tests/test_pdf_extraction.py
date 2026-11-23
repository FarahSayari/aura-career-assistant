"""Local PDF extraction tests; all PDFs are generated in memory from synthetic content."""

from collections.abc import Callable

import pymupdf
import pytest

from aura.services.pdf_extraction import PdfExtractionError, _normalize_text, extract_pdf_text


def test_valid_one_page_pdf_and_metadata(make_pdf: Callable[[list[str]], bytes]) -> None:
    pdf = make_pdf(["Alex Example\nPython Developer\nSkills: Python, SQL"])

    result = extract_pdf_text(pdf)

    assert result.page_count == 1
    assert result.pages[0].page_number == 1
    assert "Alex Example" in result.text
    assert "Python Developer\nSkills: Python, SQL" in result.pages[0].text
    assert result.file_size_bytes == len(pdf)
    assert result.metadata["title"] == "Synthetic CV"
    assert result.metadata["author"] == "Synthetic Person"
    assert result.metadata["format"].startswith("PDF")
    assert result.was_repaired is False


def test_multiple_pages_keep_numbers_boundaries_and_blank_pages(
    make_pdf: Callable[[list[str]], bytes],
) -> None:
    result = extract_pdf_text(make_pdf(["Experience on page one", "", "Education on page three"]))

    assert result.page_count == 3
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert result.pages[1].text == ""
    assert result.text.count("\f") == 2
    assert result.text.split("\n\n\f\n\n") == [
        "Experience on page one",
        "",
        "Education on page three",
    ]


def test_text_blocks_retain_layout_and_original_indices() -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        # Write the right column first to demonstrate that source order need not be visual order.
        page.insert_text((320, 180), "Right column")
        page.insert_text((72, 72), "Left column")
        pdf = document.tobytes()

    page = extract_pdf_text(pdf).pages[0]

    assert page.width > 0 and page.height > 0
    assert [block.text for block in page.blocks] == ["Left column", "Right column"]
    assert [block.block_index for block in page.blocks] == [1, 0]
    assert page.blocks[0].bbox[0] == pytest.approx(72)
    assert page.blocks[1].bbox[0] == pytest.approx(320)
    assert all(len(block.bbox) == 4 for block in page.blocks)


def test_whitespace_normalization_preserves_meaningful_lines_and_spacing() -> None:
    assert _normalize_text("\r\nHeading  \r\n    indented  detail\t \n\n\n\nNext\xa0line\n") == (
        "Heading\n    indented  detail\n\nNext line"
    )


def test_empty_uploaded_file() -> None:
    with pytest.raises(PdfExtractionError, match="file is empty"):
        extract_pdf_text(b"")


def test_blank_pdf_has_no_extractable_text(make_pdf: Callable[[list[str]], bytes]) -> None:
    with pytest.raises(PdfExtractionError, match="No extractable text.*OCR"):
        extract_pdf_text(make_pdf([""]))


def test_image_only_pdf_requires_ocr() -> None:
    with pymupdf.open() as document:
        page = document.new_page()
        image = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), 0)
        image.clear_with(255)
        page.insert_image(page.rect, stream=image.tobytes("png"))
        pdf = document.tobytes()

    with pytest.raises(PdfExtractionError, match="OCR is not available"):
        extract_pdf_text(pdf)


@pytest.mark.parametrize("data", [b"not a PDF", b"<html>A fake PDF download</html>"])
def test_invalid_pdf_bytes(data: bytes) -> None:
    with pytest.raises(PdfExtractionError, match="not a valid PDF"):
        extract_pdf_text(data)


def test_corrupted_pdf_returns_safe_error_and_no_diagnostics(capfd: pytest.CaptureFixture) -> None:
    previous_errors = pymupdf.TOOLS.mupdf_display_errors()
    previous_warnings = pymupdf.TOOLS.mupdf_display_warnings()

    with pytest.raises(PdfExtractionError, match="corrupted or incomplete") as failure:
        extract_pdf_text(b"%PDF-1.7\nSYNTHETIC_PRIVATE_MARKER\n%%EOF")

    assert "SYNTHETIC_PRIVATE_MARKER" not in str(failure.value)
    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert pymupdf.TOOLS.mupdf_display_errors() == previous_errors
    assert pymupdf.TOOLS.mupdf_display_warnings() == previous_warnings
    assert pymupdf.TOOLS.mupdf_warnings() == ""


def test_truncated_pdf_is_rejected(make_pdf: Callable[[list[str]], bytes]) -> None:
    with pytest.raises(PdfExtractionError, match="corrupted or incomplete"):
        extract_pdf_text(make_pdf(["Synthetic experience"])[:80])


def test_recoverable_damage_is_reported(make_pdf: Callable[[list[str]], bytes]) -> None:
    pdf = make_pdf(["Recoverable synthetic text"])
    damaged = pdf[: pdf.rindex(b"\nxref")]

    result = extract_pdf_text(damaged)

    assert result.was_repaired is True
    assert "Recoverable synthetic text" in result.text


@pytest.mark.parametrize("fail_on_second_page", [False, True])
def test_document_closes_on_success_and_page_failure(
    make_pdf: Callable[[list[str]], bytes],
    monkeypatch: pytest.MonkeyPatch,
    fail_on_second_page: bool,
) -> None:
    pdf = make_pdf(["First synthetic page", "Second synthetic page"])
    opened = []
    original_open = pymupdf.open
    original_get_text = pymupdf.Page.get_text

    def track_open(*args, **kwargs):
        document = original_open(*args, **kwargs)
        opened.append(document)
        return document

    def get_text(page, *args, **kwargs):
        if fail_on_second_page and page.number == 1:
            raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")
        return original_get_text(page, *args, **kwargs)

    monkeypatch.setattr(pymupdf, "open", track_open)
    monkeypatch.setattr(pymupdf.Page, "get_text", get_text)

    if fail_on_second_page:
        with pytest.raises(PdfExtractionError, match="corrupted or incomplete") as failure:
            extract_pdf_text(pdf)
        assert "SYNTHETIC_PRIVATE_MARKER" not in str(failure.value)
    else:
        assert extract_pdf_text(pdf).page_count == 2

    assert len(opened) == 1
    assert opened[0].is_closed


@pytest.mark.parametrize("password", ["synthetic-password", ""])
def test_encrypted_pdfs_are_rejected(make_pdf: Callable[[list[str]], bytes], password: str) -> None:
    with pymupdf.open(stream=make_pdf(["Synthetic private text"]), filetype="pdf") as document:
        encrypted = document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="synthetic-owner-password",
            user_pw=password,
        )

    with pytest.raises(PdfExtractionError, match="Encrypted PDFs"):
        extract_pdf_text(encrypted)


def test_configured_file_limit_is_checked_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    def must_not_open(*args, **kwargs):
        pytest.fail("Oversized input must be rejected before PDF parsing")

    monkeypatch.setattr(pymupdf, "open", must_not_open)
    with pytest.raises(PdfExtractionError, match="1 MiB file-size limit"):
        extract_pdf_text(b"%PDF-" + b"x" * (1024 * 1024), max_size_mb=1)


def test_file_exactly_at_limit_is_accepted(make_pdf: Callable[[list[str]], bytes]) -> None:
    pdf = make_pdf(["At the size boundary"])
    # A PDF comment before startxref adds padding without changing object/xref offsets.
    offset = pdf.rindex(b"startxref")
    comment = b"%" + b"x" * (1024 * 1024 - len(pdf) - 2) + b"\n"
    padded = pdf[:offset] + comment + pdf[offset:]
    assert len(padded) == 1024 * 1024

    assert "At the size boundary" in extract_pdf_text(padded, max_size_mb=1).text


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_invalid_file_limit_configuration(limit) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        extract_pdf_text(b"%PDF-1.7", max_size_mb=limit)


def test_non_bytes_input_is_rejected() -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        extract_pdf_text("local-path.pdf")
