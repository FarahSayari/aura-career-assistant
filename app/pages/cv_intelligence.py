"""Local PDF preview followed by explicitly consented, unverified Gemini extraction."""

import streamlit as st

from aura.core.config import Settings
from aura.services.gemini_extraction import GeminiExtractionError, extract_cv_profile
from aura.services.pdf_extraction import PdfExtractionError, extract_pdf_text


def _clear_analysis() -> None:
    for key in ("cv_profile", "cv_analysis_error", "cv_gemini_consent"):
        st.session_state.pop(key, None)


def _clear_upload_results() -> None:
    _clear_analysis()
    for key in ("cv_document", "cv_pdf_error"):
        st.session_state.pop(key, None)


def main() -> None:
    settings = Settings()
    st.set_page_config(
        page_title=f"CV Intelligence | {settings.app_name}", page_icon="📄", layout="wide"
    )
    st.title("CV Intelligence")
    st.write("Upload your PDF CV and inspect its extracted text, one page at a time.")
    st.caption(
        "PDF parsing happens locally. Your upload and results stay in session memory, without disk "
        "saves. Gemini receives extracted content only after your confirmation and analysis click."
    )
    uploaded = st.file_uploader(
        "Choose a PDF CV",
        type=["pdf"],
        max_upload_size=settings.pdf_max_size_mb,
        help=f"Maximum {settings.pdf_max_size_mb} MiB. Selectable text only; no OCR yet.",
        key="cv_upload",
        on_change=_clear_upload_results,
    )
    extract_clicked = st.button("Extract document text", type="primary", disabled=uploaded is None)
    if uploaded is None:
        _clear_upload_results()
        return

    if extract_clicked:
        _clear_upload_results()
        try:
            with st.spinner("Extracting PDF text locally…"):
                st.session_state.cv_document = extract_pdf_text(
                    uploaded.getvalue(), max_size_mb=settings.pdf_max_size_mb
                )
        except PdfExtractionError as error:
            st.session_state.cv_pdf_error = str(error)
    if st.session_state.get("cv_pdf_error"):
        st.error(st.session_state.cv_pdf_error)
    result = st.session_state.get("cv_document")
    if result is None:
        return

    st.success("PDF text extracted. Review the text against your original CV.")
    page_column, size_column = st.columns(2)
    page_column.metric("Pages", result.page_count)
    size_column.metric("File size", f"{result.file_size_bytes / 1024:.1f} KiB")
    with st.expander("PDF metadata"):
        if result.metadata:
            st.json(result.metadata)
        else:
            st.caption("No embedded metadata is available.")
    st.info(
        "Clear columns are read left-to-right, each top-to-bottom. Ambiguous layouts keep the "
        "original order and show a page warning. Tables and unusual fonts may still need review. "
        "Image-only pages require OCR, which is not included yet."
    )
    if result.was_repaired:
        st.warning(
            "The PDF required repair while opening. Check the extracted text for missing content."
        )
    blank_pages = [str(page.page_number) for page in result.pages if not page.text]
    if blank_pages:
        st.warning(f"No extractable text on page(s): {', '.join(blank_pages)}.")
    for page in result.pages:
        with st.expander(f"Page {page.page_number}", expanded=True):
            if page.layout_warning:
                st.warning(page.layout_warning)
            if page.text:
                st.text_area(
                    f"Extracted text — page {page.page_number}",
                    value=page.text,
                    height=300,
                    disabled=True,
                    key=f"cv_page_{page.page_number}",
                )
            else:
                st.caption("This page contains no extractable text.")

    st.subheader("Structured CV extraction")
    st.write(
        "Gemini can turn the extracted text into a structured professional profile. This sends "
        "all extracted CV text, page numbers, and block coordinates to Google, including any "
        "contact details in that text. The PDF file itself is not sent. "
        "API quotas or charges may apply."
    )
    st.caption(
        "Review [Google's Gemini data-handling terms](https://ai.google.dev/gemini-api/terms) "
        "for your project before sending personal information."
    )
    consent = st.checkbox(
        "I confirm sending this CV's extracted content to Google for Gemini processing.",
        key="cv_gemini_consent",
    )
    if st.button("Analyze with Gemini", disabled=not consent, key="cv_analyze") and consent:
        st.session_state.pop("cv_profile", None)
        st.session_state.pop("cv_analysis_error", None)
        try:
            with st.spinner("Extracting structured facts with Gemini…"):
                st.session_state.cv_profile = extract_cv_profile(
                    result, settings=settings, document_name=uploaded.name
                )
        except GeminiExtractionError as error:
            st.session_state.cv_analysis_error = str(error)
    if st.session_state.get("cv_analysis_error"):
        st.error(st.session_state.cv_analysis_error)
    if st.session_state.get("cv_profile") is not None:
        st.subheader("Professional profile — Unverified")
        st.warning(
            "All extracted information is Unverified. Review every claim against your CV. "
            "Source references identify the input document; they do not verify factual accuracy. "
            "No records have been approved or saved."
        )
        st.json(st.session_state.cv_profile.model_dump(mode="json"))


if __name__ == "__main__":
    main()
