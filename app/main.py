"""Streamlit entry point: run with `python -m streamlit run app/main.py`."""

import streamlit as st

from aura.core.config import Settings


def main() -> None:
    """Render the M0 homepage without contacting external services."""
    settings = Settings()
    st.set_page_config(page_title=settings.app_name, page_icon="✨", layout="wide")

    st.caption(":blue[YOUR CAREER, WITH INTENTION]")
    st.title(settings.app_name)
    st.markdown("Your personal AI companion for smarter job searching.")
    st.write(
        "Aura brings your professional profile, job opportunities, applications, and interview "
        "preparation into one personal workspace. We’re building it one useful step at a time."
    )
    st.info("Project foundation is ready. Career features are Coming Soon.")

    st.subheader("Your career workspace")
    features = (
        ("CV Intelligence", "Build a verified profile from your skills, experience, and projects."),
        ("Job Matching", "Understand how a role fits your background and where you can grow."),
        ("Application Studio", "Prepare truthful, tailored cover letters and application emails."),
        ("Application Tracking", "Keep opportunities, application statuses, and notes organized."),
        ("Interview Preparation", "Practice role-specific questions and reflect on your answers."),
    )
    for start in range(0, len(features), 2):
        columns = st.columns(2)
        for column, (title, description) in zip(columns, features[start : start + 2], strict=False):
            with column, st.container(border=True):
                st.subheader(title)
                st.caption(":primary[Coming Soon]")
                st.write(description)

    st.divider()
    st.caption("Built for a thoughtful job search. You stay in control of your career decisions.")


if __name__ == "__main__":
    main()
