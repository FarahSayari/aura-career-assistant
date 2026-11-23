"""Synthetic geometric layouts; no personal content, fixture PDFs, or semantic heuristics."""

import pymupdf
import pytest

from aura.services.pdf_extraction import (
    PdfTextBlock,
    _local_column_order,
    _normalize_text,
    extract_pdf_text,
)


def make_layout(items: list[tuple[float, float, str]]) -> bytes:
    """Write positioned text in caller-supplied content-stream order, entirely in memory."""
    with pymupdf.open() as document:
        page = document.new_page(width=650, height=842)
        for x, y, text in items:
            page.insert_text((x, y), text)
        document.set_metadata({"title": "Synthetic layout"})
        return document.tobytes()


def original_blocks(pdf: bytes) -> list[tuple[str, tuple[float, ...], int]]:
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        return [
            (_normalize_text(block[4]), tuple(block[:4]), block[5])
            for block in document[0].get_text("blocks", sort=True)
            if block[6] == 0 and _normalize_text(block[4])
        ]


def test_single_column_keeps_original_order_and_headings() -> None:
    pdf = make_layout(
        [
            (50, 60, "Section heading"),
            (50, 120, "First paragraph\nSecond line"),
            (50, 190, "Next item"),
        ]
    )

    page = extract_pdf_text(pdf).pages[0]

    assert page.text == "\n\n".join(text for text, _, _ in original_blocks(pdf))
    assert page.layout_warning is None


@pytest.mark.parametrize("column_count", [2, 3])
def test_columns_keep_headings_and_multiline_continuations_together(column_count: int) -> None:
    items = []
    expected = []
    for column in range(column_count):
        x = 50 + column * 200
        label = chr(ord("A") + column)
        heading = f"Category {label}"
        continuation = f"{label} first detail\n{label} continued detail"
        items.extend([(x, 90 + column * 10, heading), (x, 160 + column * 10, continuation)])
        expected.extend([heading, continuation])
    pdf = make_layout(items)
    baseline = original_blocks(pdf)

    result = extract_pdf_text(pdf)
    page = result.pages[0]

    assert [block.text for block in page.blocks] == expected
    assert [text for text, _, _ in baseline] != expected  # Original sorting interleaved columns.
    assert page.layout_warning is None
    assert result.metadata["title"] == "Synthetic layout"
    assert result.page_count == 1
    assert result.file_size_bytes == len(pdf)
    assert sorted((block.text, block.bbox, block.block_index) for block in page.blocks) == sorted(
        baseline
    )  # No original block text, coordinates, or indices were rewritten.


@pytest.mark.parametrize("column_count", [2, 3])
def test_spanning_headings_split_sections_before_column_ordering(column_count: int) -> None:
    first_heading = "FIRST SHARED SECTION HEADING SPANNING EVERY COLUMN ON THIS PAGE"
    next_heading = "NEXT SHARED SECTION HEADING SPANNING EVERY COLUMN ON THIS PAGE"
    items = [(50, 50, first_heading), (50, 280, next_heading)]
    expected = [first_heading]
    for section, top in enumerate([100, 330]):
        if section:
            expected.append(next_heading)
        for column in range(column_count):
            x = 50 + column * 200
            heading = f"Section {section} column {column}"
            detail = f"Detail {section}-{column}\nMore detail {section}-{column}"
            items.extend([(x, top + column * 10, heading), (x, top + 60 + column * 10, detail)])
            expected.extend([heading, detail])
    pdf = make_layout(items)

    page = extract_pdf_text(pdf).pages[0]

    assert [block.text for block in page.blocks] == expected
    assert page.layout_warning is None


@pytest.mark.parametrize(
    "items",
    [
        # One isolated label per potential column is insufficient evidence.
        [(50, 70, "First label"), (350, 170, "Second label")],
        # Separate sequential sections must not be treated as parallel columns.
        [
            (50, 70, "First section"),
            (50, 130, "First detail"),
            (350, 260, "Next section"),
            (350, 320, "Next detail"),
        ],
        # A crossing block overlaps body text; it cannot safely act as a section divider.
        [
            (50, 70, "Left heading"),
            (50, 150, "Left detail"),
            (350, 80, "Right heading"),
            (350, 160, "Right detail"),
            (50, 85, "A LONG CROSSING BLOCK THAT OVERLAPS THE RIGHT COLUMN HEADING"),
        ],
        # An unsupported third column must not be merged into the second column.
        [
            (50, 70, "First heading"),
            (50, 130, "First detail"),
            (250, 80, "Second heading"),
            (250, 140, "Second detail"),
            (450, 190, "Isolated third label"),
        ],
    ],
    ids=["sparse", "sequential-offset-sections", "overlapping-spanner", "unsupported-third-column"],
)
def test_ambiguous_layout_retains_exact_original_extraction(
    items: list[tuple[float, float, str]],
) -> None:
    pdf = make_layout(items)

    page = extract_pdf_text(pdf).pages[0]

    assert [
        (block.text, block.bbox, block.block_index) for block in page.blocks
    ] == original_blocks(pdf)
    assert page.layout_warning is not None
    assert "original position-sorted extraction" in page.layout_warning


def test_columns_already_merged_by_pdf_parser_are_not_split_or_guessed() -> None:
    pdf = make_layout(
        [
            (50, 70, "Left label"),
            (350, 70, "Right label"),
            (50, 140, "Left continuation"),
            (350, 140, "Right continuation"),
        ]
    )
    baseline = original_blocks(pdf)
    assert any("Left label\nRight label" in text for text, _, _ in baseline)

    page = extract_pdf_text(pdf).pages[0]

    assert [(block.text, block.bbox, block.block_index) for block in page.blocks] == baseline
    assert page.layout_warning is not None


def test_supported_columns_on_multiple_pages_keep_page_boundaries() -> None:
    with pymupdf.open() as document:
        for number in [1, 2]:
            page = document.new_page(width=650, height=842)
            page.insert_text((50, 80), f"Page {number} left\nLeft continuation")
            page.insert_text((350, 80), f"Page {number} right\nRight continuation")
        pdf = document.tobytes()

    result = extract_pdf_text(pdf)

    assert [page.page_number for page in result.pages] == [1, 2]
    assert all(page.layout_warning is None for page in result.pages)
    assert result.text.count("\f") == 1
    for number, text in enumerate(result.text.split("\n\n\f\n\n"), start=1):
        assert (
            text
            == f"Page {number} left\nLeft continuation\n\nPage {number} right\nRight continuation"
        )


def test_mixed_page_recovers_local_columns_with_narrow_positive_gutters() -> None:
    left = "\n".join(["A" * 26] * 8)
    middle = "\n".join(["B" * 26] * 8)
    right = ["Group C", "First detail", "Second category", "Continuation"]
    pdf = make_layout(
        [
            (50, 60, "Top section"),
            (550, 90, "Tag one"),
            (550, 160, "Tag two"),
            (50, 220, "Local section heading"),
            (50, 250, left),
            (250, 250, middle),
            *((450, 250 + index * 30, text) for index, text in enumerate(right)),
            (50, 400, "Following section"),
        ]
    )
    baseline = original_blocks(pdf)

    result = extract_pdf_text(pdf)
    page = result.pages[0]
    expected_region = [left, middle, *right]
    region_texts = set(expected_region)

    assert [block.text for block in page.blocks if block.text in region_texts] == expected_region
    assert [text for text, _, _ in baseline if text in region_texts] != expected_region
    assert "local column region was reordered" in page.layout_warning
    assert [block.text for block in page.blocks if block.text not in region_texts] == [
        text for text, _, _ in baseline if text not in region_texts
    ]
    assert sorted((block.text, block.bbox, block.block_index) for block in page.blocks) == sorted(
        baseline
    )
    assert page.text.index("Second category") < page.text.index("Continuation")
    assert page.text.index("Continuation") < page.text.index("Following section")
    assert result.metadata["title"] == "Synthetic layout"


def compact_region() -> list[PdfTextBlock]:
    """Independent synthetic geometry: two tall anchors plus a fragmented third column."""
    return [
        PdfTextBlock("C heading", (328, 200, 450, 210), 2),
        PdfTextBlock("C detail", (328, 220, 460, 230), 3),
        PdfTextBlock("C category", (328, 240, 450, 250), 4),
        PdfTextBlock("A\nB\nC\nD\nE\nF", (40, 200, 180, 260), 0),
        PdfTextBlock("G\nH\nI\nJ\nK\nL", (184, 200, 324, 260), 1),
        PdfTextBlock("C continuation", (328, 260, 470, 270), 5),
        PdfTextBlock("Next section heading", (40, 269, 150, 279), 6),
    ]


def test_local_region_preserves_following_heading_despite_small_glyph_overlap() -> None:
    blocks = compact_region()

    ordered = _local_column_order(blocks, 600)

    assert [block.block_index for block in ordered] == [0, 1, 2, 3, 4, 5, 6]
    assert ordered[-1] is blocks[-1]
    assert sorted(block.block_index for block in ordered) == sorted(
        block.block_index for block in blocks
    )


def test_local_region_rejects_gutters_that_are_too_small() -> None:
    blocks = compact_region()
    blocks[3] = PdfTextBlock(blocks[3].text, (40, 200, 183, 260), 0)

    assert _local_column_order(blocks, 600) is None


def test_local_region_does_not_cut_a_close_aligned_continuation() -> None:
    blocks = compact_region()[:-1]
    blocks.append(PdfTextBlock("More continuation", (328, 273, 470, 283), 6))

    assert _local_column_order(blocks, 600) is None


def test_local_region_does_not_overtake_intervening_content() -> None:
    blocks = compact_region()
    blocks.insert(2, PdfTextBlock("Unrelated tall paragraph", (40, 100, 590, 245), 7))

    assert _local_column_order(blocks, 600) is None
