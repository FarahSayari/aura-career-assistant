"""Synthetic profile fixtures and schema validation; no personal documents or services."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from aura.schemas import (
    AwardAchievement,
    CareerPreferences,
    Certification,
    ContactInformation,
    DateRange,
    Education,
    Identity,
    PartialDate,
    ProfessionalProfile,
    ProfessionalSummary,
    Project,
    ProjectFeature,
    ProjectStatus,
    Skill,
    SkillCategory,
    SourceReference,
    SourceType,
    SpokenLanguage,
    VerificationStatus,
    WorkExperience,
    WorkMode,
)


@pytest.fixture
def complete_profile() -> ProfessionalProfile:
    cv = {"source_type": "cv", "reference": "synthetic-cv.pdf", "locator": "Page 1"}
    portfolio = {
        "source_type": "portfolio",
        "reference": "Synthetic portfolio project page",
        "url": "https://example.com/projects/search-demo",
        "locator": "Project overview",
    }
    manual = {"source_type": "manual", "reference": "Synthetic preferences form"}
    return ProfessionalProfile.model_validate(
        {
            "identity": {
                "full_name": "Alex Example",
                "professional_title": "Software Engineer",
                "location": "Example City",
                "contact": {
                    "email": "alex@example.com",
                    "phone": "+1 202 555 0100",
                    "links": ["https://example.com/contact"],
                    "sources": [cv],
                },
                "sources": [cv, portfolio],
            },
            "professional_summary": {
                "text": "Builds small, tested Python applications.",
                "sources": [cv],
            },
            "technical_skills": [
                {
                    "name": "Languages",
                    "skills": [
                        {"name": "Python", "sources": [cv, portfolio]},
                        {"name": "SQL", "sources": [cv]},
                    ],
                },
                {
                    "name": "Frameworks",
                    "skills": [{"name": "Streamlit", "sources": [portfolio]}],
                },
            ],
            "work_experience": [
                {
                    "organization": "Example Labs",
                    "role": "Software Intern",
                    "location": "Example City",
                    "dates": {
                        "start": {"year": 2024, "month": 6},
                        "end": {"year": 2024, "month": 9},
                        "is_current": False,
                    },
                    "responsibilities": ["Wrote validation tests."],
                    "achievements": ["Delivered a reviewed test suite."],
                    "sources": [cv],
                }
            ],
            "education": [
                {
                    "institution": "Example University",
                    "degree": "BSc",
                    "specialization": "Computer Science",
                    "dates": {"start": {"year": 2021}, "end": {"year": 2024}},
                    "sources": [cv],
                }
            ],
            "projects": [
                {
                    "name": "Search Demo",
                    "status": "completed",
                    "description": "A small local document search demonstration.",
                    "technologies": ["Python", "Streamlit"],
                    "responsibilities": ["Implemented the interface and tests."],
                    "achievements": ["Published a working demonstration."],
                    "dates": {
                        "start": {"year": 2024, "month": 10},
                        "end": {"year": 2025, "month": 1, "day": 15},
                    },
                    "links": [
                        "https://example.com/projects/search-demo",
                        "https://github.com/example/search-demo",
                    ],
                    "sources": [cv, portfolio],
                }
            ],
            "certifications": [
                {
                    "name": "Synthetic Python Certificate",
                    "issuer": "Example Academy",
                    "issued_on": {"year": 2024, "month": 5, "day": 20},
                    "expires_on": {"year": 2027, "month": 5},
                    "url": "https://example.com/credentials/demo",
                    "sources": [cv],
                }
            ],
            "awards": [
                {
                    "title": "Synthetic Student Project Award",
                    "description": "Recognized for a student team demonstration.",
                    "issuer": "Example University",
                    "awarded_on": {"year": 2024},
                    "url": "https://example.com/awards/demo",
                    "sources": [cv],
                }
            ],
            "spoken_languages": [
                {"language": "English", "proficiency": "B2", "sources": [cv]},
                {"language": "French", "sources": [cv]},
            ],
            "career_preferences": {
                "target_roles": ["AI Engineer", "Python Developer"],
                "preferred_locations": ["Example City"],
                "work_modes": ["remote", "hybrid", "on_site"],
                "sources": [manual],
            },
        }
    )


def test_minimal_valid_profile() -> None:
    profile = ProfessionalProfile(identity={"full_name": "Alex Example"})

    assert profile.identity.full_name == "Alex Example"
    assert profile.identity.professional_title is None
    assert profile.identity.contact is None
    assert profile.professional_summary is None
    assert profile.career_preferences is None
    assert profile.projects == []


def test_empty_profile_keeps_facts_unknown() -> None:
    profile = ProfessionalProfile()

    assert profile.identity.full_name is None
    assert profile.identity.location is None
    assert profile.identity.verification_status == VerificationStatus.UNVERIFIED
    assert profile.work_experience == []


def test_complete_synthetic_profile(complete_profile: ProfessionalProfile) -> None:
    assert complete_profile.identity.contact.email == "alex@example.com"
    assert complete_profile.professional_summary.text.startswith("Builds small")
    assert complete_profile.work_experience[0].organization == "Example Labs"
    assert complete_profile.education[0].specialization == "Computer Science"
    assert complete_profile.certifications[0].issued_on.day == 20
    assert complete_profile.awards[0].awarded_on.month is None
    assert complete_profile.spoken_languages[1].proficiency is None
    assert complete_profile.career_preferences.work_modes == list(WorkMode)


def test_multiple_skills_and_categories(complete_profile: ProfessionalProfile) -> None:
    categories = complete_profile.technical_skills

    assert [category.name for category in categories] == ["Languages", "Frameworks"]
    assert [skill.name for skill in categories[0].skills] == ["Python", "SQL"]
    assert categories[1].skills[0].name == "Streamlit"
    assert len(categories[0].skills[0].sources) == 2


def test_project_supports_multiple_sources_and_repository_references(
    complete_profile: ProfessionalProfile,
) -> None:
    project = complete_profile.projects[0]

    assert [source.source_type for source in project.sources] == [
        SourceType.CV,
        SourceType.PORTFOLIO,
    ]
    assert project.sources[0].locator == "Page 1"
    assert str(project.sources[1].url) == "https://example.com/projects/search-demo"
    assert str(project.links[1]) == "https://github.com/example/search-demo"


@pytest.mark.parametrize("status", ["completed", "in_progress", "planned", "unknown"])
def test_project_status_is_explicit_and_preserved(status: str) -> None:
    project = Project(name="Synthetic project", status=status)

    assert project.status.value == status
    assert project.verification_status == VerificationStatus.UNVERIFIED


def test_missing_project_status_stays_unknown_and_unverified() -> None:
    project = Project(name="Synthetic project")

    assert project.status == ProjectStatus.UNKNOWN
    assert project.verification_status == VerificationStatus.UNVERIFIED
    assert project.features == []


@pytest.mark.parametrize("dates", [{"is_current": True}, {"end": {"year": 2025}}, None])
def test_reported_dates_and_achievements_do_not_infer_project_status(
    dates: dict[str, Any] | None,
) -> None:
    project = Project(
        name="Synthetic project", dates=dates, achievements=["Delivered a prototype."]
    )

    assert project.status == ProjectStatus.UNKNOWN
    assert project.verification_status == VerificationStatus.UNVERIFIED


def test_ongoing_project_supports_mixed_feature_statuses() -> None:
    project = Project(
        name="Synthetic dashboard",
        status="in_progress",
        features=[
            {
                "name": "Local search",
                "description": "Search a local synthetic dataset.",
                "status": "completed",
                "sources": [{"source_type": "portfolio", "reference": "Demo capabilities"}],
            },
            {"name": "Filters", "status": "in_progress"},
            {"name": "Exports", "status": "planned"},
            {"name": "Notifications"},
        ],
    )

    assert [feature.status for feature in project.features] == list(ProjectStatus)
    assert project.features[0].description == "Search a local synthetic dataset."
    assert project.features[0].sources[0].source_type == SourceType.PORTFOLIO
    assert all(
        feature.verification_status == VerificationStatus.UNVERIFIED for feature in project.features
    )
    assert project.status == ProjectStatus.IN_PROGRESS


def test_feature_status_and_parent_review_do_not_imply_feature_verification() -> None:
    project = Project(
        name="Reviewed project",
        verification_status="verified",
        features=[{"name": "Reported capability", "status": "completed"}],
    )

    assert project.status == ProjectStatus.UNKNOWN
    assert project.verification_status == VerificationStatus.VERIFIED
    assert project.features[0].status == ProjectStatus.COMPLETED
    assert project.features[0].verification_status == VerificationStatus.UNVERIFIED


def test_feature_defaults_preserve_unknown_information() -> None:
    feature = ProjectFeature(name="Reported capability")

    assert feature.description is None
    assert feature.status == ProjectStatus.UNKNOWN
    assert feature.verification_status == VerificationStatus.UNVERIFIED
    assert feature.sources == []


def test_project_feature_list_defaults_are_independent() -> None:
    first = Project(name="First project")
    second = Project(name="Second project")
    first.features.append(ProjectFeature(name="Local search"))

    assert second.features == []


def test_planned_project_cannot_claim_achievements() -> None:
    with pytest.raises(ValidationError, match="Planned projects"):
        Project(name="Future demo", status="planned", achievements=["Delivered a product."])


@pytest.mark.parametrize("status", ["planned", "completed"])
def test_completed_or_planned_projects_cannot_have_current_dates(status: str) -> None:
    with pytest.raises(ValidationError, match="ongoing period"):
        Project(name="Synthetic project", status=status, dates={"is_current": True})


@pytest.mark.parametrize("dates", [{"end": {"year": 2025}}, {"is_current": False}])
def test_ongoing_project_cannot_have_an_ended_period(dates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="ended period"):
        Project(name="Synthetic project", status="in_progress", dates=dates)


def test_current_project_accepts_unknown_start_date() -> None:
    project = Project(name="Active demo", status="in_progress", dates={"is_current": True})

    assert project.dates.start is None
    assert project.dates.is_current is True


def test_all_extracted_records_start_unverified(complete_profile: ProfessionalProfile) -> None:
    records = [
        complete_profile.identity,
        complete_profile.identity.contact,
        complete_profile.professional_summary,
        *(skill for group in complete_profile.technical_skills for skill in group.skills),
        *complete_profile.work_experience,
        *complete_profile.education,
        *complete_profile.projects,
        *complete_profile.certifications,
        *complete_profile.awards,
        *complete_profile.spoken_languages,
        complete_profile.career_preferences,
    ]

    assert all(record.verification_status == VerificationStatus.UNVERIFIED for record in records)


@pytest.mark.parametrize("status", ["unverified", "verified", "rejected"])
def test_verification_status_can_be_set_explicitly(status: str) -> None:
    skill = Skill(name="Python", verification_status=status)

    assert skill.verification_status.value == status


def test_review_of_one_record_does_not_verify_other_records() -> None:
    profile = ProfessionalProfile(
        identity={
            "full_name": "Alex Example",
            "verification_status": "verified",
            "contact": {"email": "alex@example.com"},
        },
        technical_skills=[{"name": "Languages", "skills": [{"name": "Python"}]}],
    )

    assert profile.identity.verification_status == VerificationStatus.VERIFIED
    assert profile.identity.contact.verification_status == VerificationStatus.UNVERIFIED
    assert (
        profile.technical_skills[0].skills[0].verification_status == VerificationStatus.UNVERIFIED
    )


@pytest.mark.parametrize("url", ["not-a-url", "ftp://example.com/file", "javascript:alert(1)"])
@pytest.mark.parametrize("record_type", ["project", "source", "certification", "contact", "award"])
def test_invalid_urls_are_rejected(url: str, record_type: str) -> None:
    with pytest.raises(ValidationError):
        match record_type:
            case "project":
                Project(name="Demo", status="planned", links=[url])
            case "source":
                SourceReference(source_type="portfolio", reference="Demo", url=url)
            case "certification":
                Certification(name="Demo", url=url)
            case "contact":
                ContactInformation(links=[url])
            case "award":
                AwardAchievement(title="Demo", url=url)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (Project, {"name": "Demo", "status": "done"}),
        (ProjectFeature, {"name": "Demo capability", "status": "done"}),
        (Skill, {"name": "Python", "verification_status": "approved"}),
        (SourceReference, {"source_type": "github", "reference": "Repository"}),
        (CareerPreferences, {"work_modes": ["anywhere"]}),
    ],
)
def test_invalid_enum_values_are_rejected(model, data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(
    "data",
    [
        {"year": 2024},
        {"year": 2024, "month": 2},
        {"year": 2024, "month": 2, "day": 29},
    ],
)
def test_partial_dates_preserve_reported_precision(data: dict[str, int]) -> None:
    reported = PartialDate.model_validate(data)

    assert reported.model_dump(exclude_none=True) == data
    assert PartialDate.model_validate_json(reported.model_dump_json()) == reported


@pytest.mark.parametrize(
    "data",
    [
        {"year": 0},
        {"year": 10000},
        {"year": True},
        {"year": "2024"},
        {"year": 2024, "month": 13},
        {"year": 2024, "month": 0},
        {"year": 2024, "day": 10},
        {"year": 2023, "month": 2, "day": 29},
        {"year": 2024, "month": 4, "day": 31},
        {"year": 2024, "month": 2, "day": 0},
        {"month": 2},
    ],
)
def test_invalid_calendar_dates_are_rejected(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PartialDate.model_validate(data)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ({"year": 2025}, {"year": 2024}),
        ({"year": 2024, "month": 9}, {"year": 2024, "month": 8}),
        ({"year": 2024, "month": 2, "day": 20}, {"year": 2024, "month": 2, "day": 19}),
    ],
)
def test_reversed_date_ranges_are_rejected(start: dict[str, int], end: dict[str, int]) -> None:
    with pytest.raises(ValidationError, match="precede"):
        DateRange(start=start, end=end)


def test_uncertain_date_order_does_not_invent_precision() -> None:
    dates = DateRange(start={"year": 2024, "month": 9}, end={"year": 2024})

    assert dates.end.month is None
    assert dates.start.day is None


def test_unknown_end_does_not_imply_current_employment() -> None:
    experience = WorkExperience(role="Intern", dates={"start": {"year": 2024}})

    assert experience.organization is None
    assert experience.dates.end is None
    assert experience.dates.is_current is None


def test_current_period_cannot_have_end_date() -> None:
    with pytest.raises(ValidationError, match="ongoing period"):
        DateRange(end={"year": 2025}, is_current=True)


def test_certification_expiry_cannot_precede_issue_date() -> None:
    with pytest.raises(ValidationError, match="precede"):
        Certification(name="Demo", issued_on={"year": 2025}, expires_on={"year": 2024})


@pytest.mark.parametrize("source_type", ["cv", "portfolio"])
def test_preferences_cannot_be_extracted_from_documents(source_type: str) -> None:
    with pytest.raises(ValidationError, match="manual source"):
        CareerPreferences(sources=[{"source_type": source_type, "reference": "Synthetic input"}])


def test_list_defaults_are_independent() -> None:
    first = ProfessionalProfile()
    second = ProfessionalProfile()
    first.projects.append(Project(name="Demo", status=ProjectStatus.PLANNED))
    first.identity.sources.append(SourceReference(source_type="manual", reference="Review"))

    assert second.projects == []
    assert second.identity.sources == []
    first_group = SkillCategory(name="Languages")
    second_group = SkillCategory(name="Languages")
    first_group.skills.append(Skill(name="Python"))
    assert second_group.skills == []


def test_empty_values_and_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Skill(name="   ")
    with pytest.raises(ValidationError):
        ProfessionalProfile(unknown_fact="Do not silently discard this")
    with pytest.raises(ValidationError):
        ProfessionalProfile(identity={"full_nmae": "Alex Example"})


def test_optional_fields_can_be_missing() -> None:
    assert Education(institution="Example University").degree is None
    assert Certification(name="Demo").issued_on is None
    assert ProfessionalSummary(text="Reported summary").sources == []
    assert SpokenLanguage(language="English").proficiency is None
    assert Identity(full_name="Alex Example").contact is None


def test_complete_profile_json_round_trip(complete_profile: ProfessionalProfile) -> None:
    serialized = complete_profile.model_dump_json()
    data = json.loads(serialized)

    assert data["projects"][0]["status"] == "completed"
    assert data["projects"][0]["sources"][1]["source_type"] == "portfolio"
    assert data["education"][0]["dates"]["start"] == {
        "year": 2021,
        "month": None,
        "day": None,
    }
    assert ProfessionalProfile.model_validate_json(serialized) == complete_profile
    assert (
        ProfessionalProfile.model_validate(complete_profile.model_dump(mode="json"))
        == complete_profile
    )


def test_profile_json_preserves_unknown_and_mixed_feature_statuses() -> None:
    profile = ProfessionalProfile(
        projects=[
            {
                "name": "Synthetic dashboard",
                "features": [
                    {"name": "Search", "status": "completed"},
                    {"name": "Filters", "status": "in_progress"},
                    {"name": "Exports", "status": "planned"},
                    {"name": "Notifications"},
                ],
            }
        ]
    )
    serialized = profile.model_dump_json()
    data = json.loads(serialized)

    assert data["projects"][0]["status"] == "unknown"
    assert [feature["status"] for feature in data["projects"][0]["features"]] == [
        "completed",
        "in_progress",
        "planned",
        "unknown",
    ]
    assert all(
        feature["verification_status"] == "unverified"
        for feature in data["projects"][0]["features"]
    )
    assert ProfessionalProfile.model_validate_json(serialized) == profile


def test_schema_exposes_descriptions_and_enum_choices() -> None:
    schema = ProfessionalProfile.model_json_schema()

    assert schema["properties"]["technical_skills"]["description"]
    assert schema["$defs"]["ProjectStatus"]["enum"] == [
        "completed",
        "in_progress",
        "planned",
        "unknown",
    ]
    assert schema["$defs"]["SourceType"]["enum"] == ["cv", "portfolio", "manual"]
