"""Local, in-memory PDF text extraction with page and layout provenance."""

import re
from bisect import bisect_right
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import combinations, pairwise
from statistics import median
from threading import Lock

import pymupdf

from aura.core.config import DEFAULT_PDF_MAX_SIZE_MB

_PARSER_LOCK = Lock()
_LAYOUT_FALLBACK = (
    "Column reading order is ambiguous on this page. The original position-sorted extraction "
    "was retained; compare it with the PDF."
)
_LOCAL_LAYOUT_WARNING = (
    "A clear local column region was reordered. Other page regions retain their original "
    "position-sorted order; compare complex layouts with the PDF."
)


class PdfExtractionError(ValueError):
    """An expected upload/parsing failure with a message safe to display to the user."""


@dataclass(frozen=True)
class PdfTextBlock:
    text: str
    bbox: tuple[float, float, float, float]
    block_index: int  # Original zero-based block index, before position-based sorting.


@dataclass(frozen=True)
class PdfPage:
    page_number: int  # One-based, matching the source document.
    width: float
    height: float
    blocks: tuple[PdfTextBlock, ...]
    layout_warning: str | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks)


@dataclass(frozen=True)
class ExtractedPdf:
    pages: tuple[PdfPage, ...]
    metadata: dict[str, str]
    file_size_bytes: int
    was_repaired: bool

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def text(self) -> str:
        """Full text with a form-feed separator for each original page boundary."""
        return "\n\n\f\n\n".join(page.text for page in self.pages)


def _normalize_text(text: str) -> str:
    """Trim trailing space/excess blank lines while preserving lines and indentation."""
    lines = [line.replace("\xa0", " ").expandtabs(4).rstrip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")


def _has_column_support(blocks: list[PdfTextBlock]) -> bool:
    """Require at least two reported text lines, not one isolated label."""
    return sum(len(block.text.splitlines()) for block in blocks) >= 2


def _order_column_band(
    blocks: list[PdfTextBlock], starts: list[float]
) -> list[PdfTextBlock] | None:
    """Read supported columns left-to-right, each top-to-bottom; None means ambiguous."""
    columns: list[list[PdfTextBlock]] = [[] for _ in starts]
    for block in blocks:
        column = bisect_right(starts, block.bbox[0] + 1) - 1
        if column < 0:
            return None
        columns[column].append(block)
    active = [column for column in columns if column]
    if len(active) <= 1:
        return sorted(blocks, key=lambda block: (block.bbox[1], block.bbox[0]))
    if not all(_has_column_support(column) for column in active):
        return None
    ordered = []
    for column in active:
        column.sort(key=lambda block: (block.bbox[1], block.bbox[0]))
        if any(first.bbox[3] > second.bbox[1] + 1 for first, second in pairwise(column)):
            return None  # Overlaid blocks within one column have no reliable order.
        ordered.extend(column)
    for left, right in pairwise(active):
        overlap = min(max(b.bbox[3] for b in left), max(b.bbox[3] for b in right)) - max(
            min(b.bbox[1] for b in left), min(b.bbox[1] for b in right)
        )
        if overlap <= 1:
            return None  # Horizontally offset, sequential sections are not columns.
    return ordered


def _layout_order(
    blocks: list[PdfTextBlock], page_width: float, *, minimum_gutter: float | None = None
) -> tuple[tuple[PdfTextBlock, ...], str | None]:
    """Conservatively order two/three columns separated by clear horizontal whitespace.

    Left-edge clusters must be at least 12% of the page width apart. Each column
    needs two text lines and vertical overlap with its neighbor. Blocks crossing
    a gutter may divide sections only when vertically separate from all body text.
    Any uncertain band leaves the entire original page ordering unchanged.
    """
    original = tuple(blocks)
    if not blocks:
        return original, None
    clusters: list[list[PdfTextBlock]] = []
    for block in sorted(blocks, key=lambda block: block.bbox[0]):
        if not clusters or block.bbox[0] - clusters[-1][0].bbox[0] >= page_width * 0.12:
            clusters.append([])
        clusters[-1].append(block)
    if len(clusters) == 1:
        return original, None
    starts = [cluster[0].bbox[0] for cluster in clusters if _has_column_support(cluster)]
    if not 2 <= len(starts) <= 3:
        return original, _LAYOUT_FALLBACK

    body, dividers = [], []
    gutter = max(12.0, page_width * 0.02) if minimum_gutter is None else minimum_gutter
    for block in blocks:
        column = bisect_right(starts, block.bbox[0] + 1) - 1
        if column < 0:
            return original, _LAYOUT_FALLBACK
        if column < len(starts) - 1 and block.bbox[2] > starts[column + 1] - gutter:
            # A possible spanning heading/paragraph must actually cross the gutter.
            if block.bbox[2] < starts[column + 1]:
                return original, _LAYOUT_FALLBACK
            dividers.append(block)
        else:
            if block.bbox[0] - starts[column] >= page_width * 0.12:
                return original, _LAYOUT_FALLBACK  # An unsupported extra column/offset.
            body.append(block)
    for divider in dividers:
        if any(
            block is not divider
            and min(block.bbox[3], divider.bbox[3]) - max(block.bbox[1], divider.bbox[1]) > 1
            for block in blocks
        ):
            return original, _LAYOUT_FALLBACK

    ordered = []
    remaining = body
    for divider in sorted(dividers, key=lambda block: block.bbox[1]):
        band = [block for block in remaining if block.bbox[3] <= divider.bbox[1] + 1]
        band_order = _order_column_band(band, starts)
        if band_order is None:
            return original, _LAYOUT_FALLBACK
        ordered.extend(band_order)
        ordered.append(divider)
        remaining = [block for block in remaining if block.bbox[3] > divider.bbox[1] + 1]
    band_order = _order_column_band(remaining, starts)
    if band_order is None:
        return original, _LAYOUT_FALLBACK
    ordered.extend(band_order)
    return tuple(ordered), None


def _local_column_order(
    blocks: list[PdfTextBlock], page_width: float
) -> tuple[PdfTextBlock, ...] | None:
    """Recover compact column regions inside otherwise mixed-layout pages.

    Two side-by-side multiline blocks with matching vertical extents anchor a
    region. Allow one estimated text-line of height variation for neighboring
    columns, but never cut a block, overtake intervening content, or split a close
    continuation. Existing column confidence checks still apply inside the region.
    """
    anchors = sorted(
        (block for block in blocks if _has_column_support([block])),
        key=lambda block: block.bbox[0],
    )
    regions: dict[tuple[int, ...], tuple[PdfTextBlock, ...]] = {}
    for left, right in combinations(anchors, 2):
        line_height = median(
            (block.bbox[3] - block.bbox[1]) / len(block.text.splitlines())
            for block in (left, right)
        )
        gutter = max(2.0, line_height * 0.25)
        if (
            right.bbox[0] - left.bbox[0] < page_width * 0.12
            or right.bbox[0] - left.bbox[2] < gutter
            or abs(left.bbox[1] - right.bbox[1]) > line_height
            or abs(left.bbox[3] - right.bbox[3]) > line_height
        ):
            continue
        top = min(left.bbox[1], right.bbox[1])
        bottom = max(left.bbox[3], right.bbox[3]) + line_height
        positions = tuple(
            index
            for index, block in enumerate(blocks)
            if block.bbox[1] >= top - 1 and block.bbox[3] <= bottom
        )
        if not positions or positions != tuple(range(positions[0], positions[-1] + 1)):
            continue  # Moving this region would overtake unrelated content.
        region = [blocks[index] for index in positions]
        region_bottom = max(block.bbox[3] for block in region)
        outsiders = blocks[: positions[0]] + blocks[positions[-1] + 1 :]
        if any(
            min(block.bbox[3], region_bottom) - max(block.bbox[1], top) > line_height * 0.25
            for block in outsiders
        ):
            continue  # A region boundary would cut overlapping content.
        if any(
            abs(block.bbox[0] - member.bbox[0]) <= line_height * 0.25
            and 0 <= block.bbox[1] - member.bbox[3] <= line_height * 0.5
            for block in outsiders
            for member in region
        ):
            continue  # A close aligned continuation would be left outside.
        ordered, warning = _layout_order(region, page_width, minimum_gutter=gutter)
        if warning is None:
            regions[positions] = ordered

    result = list(blocks)
    for positions, ordered in regions.items():
        if any(
            other != positions and other[0] <= positions[-1] and positions[0] <= other[-1]
            for other in regions
        ):
            continue  # Competing region interpretations remain untouched.
        result[positions[0] : positions[-1] + 1] = ordered
    return tuple(result) if result != blocks else None


def _has_merged_or_rotated_text(page: pymupdf.Page, flags: int) -> bool:
    """Detect unsafe blocks; do not split or rewrite PyMuPDF's original text blocks."""
    for block in page.get_text("dict", flags=flags)["blocks"]:
        lines = sorted(block.get("lines", []), key=lambda line: (line["bbox"][1], line["bbox"][0]))
        if any(line["dir"] != (1.0, 0.0) for line in lines):
            return True
        for first, second in pairwise(lines):
            a, b = first["bbox"], second["bbox"]
            overlap = min(a[3], b[3]) - max(a[1], b[1])
            horizontal_gap = max(a[0], b[0]) - min(a[2], b[2])
            if horizontal_gap >= 12 and overlap >= 0.5 * min(a[3] - a[1], b[3] - b[1]):
                return True  # Separate column lines were already merged into one block.
    return False


@contextmanager
def _quiet_parser() -> Iterator[None]:
    """Keep native diagnostics out of logs and restore process-wide parser settings."""
    # MuPDF diagnostic settings are global; serialize this service's parsing calls.
    with _PARSER_LOCK:
        previous_errors = pymupdf.TOOLS.mupdf_display_errors()
        previous_warnings = pymupdf.TOOLS.mupdf_display_warnings()
        pymupdf.TOOLS.mupdf_display_errors(False)
        pymupdf.TOOLS.mupdf_display_warnings(False)
        try:
            yield
        finally:
            pymupdf.TOOLS.reset_mupdf_warnings()
            pymupdf.TOOLS.mupdf_display_errors(previous_errors)
            pymupdf.TOOLS.mupdf_display_warnings(previous_warnings)


def extract_pdf_text(
    pdf_bytes: bytes, *, max_size_mb: int = DEFAULT_PDF_MAX_SIZE_MB
) -> ExtractedPdf:
    """Extract every page without OCR, network access, disk writes, or profile inference.

    Clear two/three-column regions are read column-by-column. Ambiguous layouts
    retain the original position-sorted extraction and receive a page warning.
    Coordinates and original block indices remain available for later stages.
    """
    if isinstance(max_size_mb, bool) or not isinstance(max_size_mb, int) or max_size_mb < 1:
        raise ValueError("max_size_mb must be a positive integer.")
    if not isinstance(pdf_bytes, bytes):
        raise TypeError("pdf_bytes must be bytes from an uploaded PDF.")
    if not pdf_bytes:
        raise PdfExtractionError("The uploaded file is empty. Choose a PDF containing CV text.")
    if len(pdf_bytes) > max_size_mb * 1024 * 1024:
        raise PdfExtractionError(f"The PDF exceeds the {max_size_mb} MiB file-size limit.")
    if b"%PDF-" not in pdf_bytes[:1024]:
        raise PdfExtractionError("The uploaded file is not a valid PDF. Choose a PDF document.")

    try:
        with _quiet_parser(), pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
            if not document.is_pdf:
                raise PdfExtractionError("The uploaded file is not a PDF document.")
            if document.needs_pass or document.is_encrypted:
                raise PdfExtractionError(
                    "Encrypted PDFs are not supported. Upload an unencrypted copy of your CV."
                )
            metadata = {key: value for key, value in (document.metadata or {}).items() if value}
            if metadata.get("encryption"):
                raise PdfExtractionError(
                    "Encrypted PDFs are not supported. Upload an unencrypted copy of your CV."
                )
            if document.page_count == 0:
                raise PdfExtractionError(
                    "The PDF contains no pages. Choose a PDF containing CV text."
                )

            pages = []
            for page in document:
                blocks = []
                # Image blocks are excluded; images are never converted to text in M1.2a.
                flags = pymupdf.TEXTFLAGS_BLOCKS & ~pymupdf.TEXT_PRESERVE_IMAGES
                for block in page.get_text("blocks", flags=flags, sort=True):
                    if block[6] != 0:
                        continue
                    text = _normalize_text(block[4])
                    if text:
                        blocks.append(PdfTextBlock(text, tuple(block[:4]), block[5]))
                ordered_blocks, warning = _layout_order(blocks, page.rect.width)
                if _has_merged_or_rotated_text(page, flags):
                    ordered_blocks, warning = tuple(blocks), _LAYOUT_FALLBACK
                elif warning is not None:
                    local_order = _local_column_order(blocks, page.rect.width)
                    if local_order is not None:
                        ordered_blocks, warning = local_order, _LOCAL_LAYOUT_WARNING
                pages.append(
                    PdfPage(
                        page.number + 1, page.rect.width, page.rect.height, ordered_blocks, warning
                    )
                )

            if not any(page.text.strip() for page in pages):
                raise PdfExtractionError(
                    "No extractable text was found. The PDF may be scanned, image-based, or blank. "
                    "OCR is not available yet; use a PDF with selectable text."
                )
            return ExtractedPdf(tuple(pages), metadata, len(pdf_bytes), document.is_repaired)
    except PdfExtractionError:
        raise
    except (RuntimeError, ValueError, pymupdf.mupdf.FzErrorBase):
        # Native error details can contain document fragments; never display or log them.
        raise PdfExtractionError(
            "The PDF could not be read. It may be corrupted or incomplete. "
            "Try exporting a fresh PDF and uploading it again."
        ) from None
