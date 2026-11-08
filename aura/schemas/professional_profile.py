"""Professional profile facts and provenance; no ingestion, storage, or AI calls."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SourceType(StrEnum):
    CV = "cv"
    PORTFOLIO = "portfolio"
    MANUAL = "manual"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ProjectStatus(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    PLANNED = "planned"
    UNKNOWN = "unknown"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"


class ProfileModel(BaseModel):
    """Reject unknown fields instead of silently discarding extraction mistakes."""

    model_config = ConfigDict(extra="forbid")


class PartialDate(ProfileModel):
    """Retain reported date precision; use None for a completely unknown date."""

    year: int = Field(ge=1, le=9999, strict=True, description="Reported calendar year.")
    month: int | None = Field(
        default=None, ge=1, le=12, strict=True, description="Reported month, or null if unknown."
    )
    day: int | None = Field(
        default=None, ge=1, le=31, strict=True, description="Reported day, only if month is known."
    )

    @model_validator(mode="after")
    def validate_calendar_date(self) -> Self:
        if self.day is not None:
            if self.month is None:
                raise ValueError("A day requires a known month.")
            # Construct a date only when all three components were actually supplied.
            date(self.year, self.month, self.day)
        return self


class DateRange(ProfileModel):
    """A reported period; missing end dates do not imply that work is current."""

    start: PartialDate | None = Field(default=None, description="Reported start date, if known.")
    end: PartialDate | None = Field(default=None, description="Reported end date, if known.")
    is_current: bool | None = Field(
        default=None, description="True only if explicitly reported as ongoing; null if unknown."
    )

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.is_current is True and self.end is not None:
            raise ValueError("An ongoing period cannot have a reported end date.")
        if self.start is not None and self.end is not None:
            start_parts = (self.start.year, self.start.month, self.start.day)
            end_parts = (self.end.year, self.end.month, self.end.day)
            # Compare only shared precision; overlapping uncertain dates remain valid.
            for start_part, end_part in zip(start_parts, end_parts, strict=True):
                if start_part is None or end_part is None or start_part < end_part:
                    break
                if start_part > end_part:
                    raise ValueError("End date cannot precede start date.")
        return self


class SourceReference(ProfileModel):
    """A pointer to evidence, not a copy of a CV or a scraped portfolio document."""

    source_type: SourceType = Field(description="Evidence origin: cv, portfolio, or manual.")
    reference: NonEmptyText = Field(
        description="Document name, portfolio page title, or manual input identifier."
    )
    locator: NonEmptyText | None = Field(
        default=None, description="Optional page, section, or other location within the source."
    )
    url: HttpUrl | None = Field(default=None, description="HTTP(S) evidence URL, if available.")


class EvidenceRecord(ProfileModel):
    """Review applies to this record; nested records retain their own review states."""

    sources: list[SourceReference] = Field(
        default_factory=list, description="All known supporting source references for this record."
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.UNVERIFIED,
        description="Unverified until explicitly reviewed; rejected records are not trusted facts.",
    )


class ContactInformation(EvidenceRecord):
    email: NonEmptyText | None = Field(
        default=None, description="Reported email address, if known."
    )
    phone: NonEmptyText | None = Field(default=None, description="Reported phone number, if known.")
    links: list[HttpUrl] = Field(
        default_factory=list, description="Public professional contact URLs."
    )


class Identity(EvidenceRecord):
    full_name: NonEmptyText | None = Field(
        default=None, description="Reported full name, if known."
    )
    professional_title: NonEmptyText | None = Field(
        default=None, description="Reported professional title; do not infer seniority."
    )
    location: NonEmptyText | None = Field(
        default=None, description="Reported city, region, or country."
    )
    contact: ContactInformation | None = Field(
        default=None, description="Optional contact information with its own provenance and review."
    )


class ProfessionalSummary(EvidenceRecord):
    text: NonEmptyText = Field(
        description="Professional summary supported by the referenced sources."
    )


class Skill(EvidenceRecord):
    name: NonEmptyText = Field(
        description="Reported technical skill; never infer it from a job title."
    )


class SkillCategory(ProfileModel):
    """A grouping label; each skill carries its own evidence and verification status."""

    name: NonEmptyText = Field(description="Skill group, such as languages, frameworks, or tools.")
    skills: list[Skill] = Field(default_factory=list, description="Individually reviewable skills.")


class WorkExperience(EvidenceRecord):
    organization: NonEmptyText | None = Field(
        default=None, description="Reported employer or client."
    )
    role: NonEmptyText | None = Field(default=None, description="Reported position or role title.")
    location: NonEmptyText | None = Field(
        default=None, description="Reported work location, if known."
    )
    dates: DateRange | None = Field(
        default=None, description="Reported employment period, if known."
    )
    responsibilities: list[NonEmptyText] = Field(
        default_factory=list, description="Reported duties; do not invent responsibilities."
    )
    achievements: list[NonEmptyText] = Field(
        default_factory=list,
        description="Reported outcomes; do not invent metrics or achievements.",
    )


class Education(EvidenceRecord):
    institution: NonEmptyText | None = Field(
        default=None, description="Reported school or university."
    )
    degree: NonEmptyText | None = Field(
        default=None, description="Reported degree or qualification."
    )
    specialization: NonEmptyText | None = Field(
        default=None, description="Reported field of study."
    )
    dates: DateRange | None = Field(default=None, description="Reported study period, if known.")


class ProjectFeature(EvidenceRecord):
    """A reported capability; implementation status and verification remain independent."""

    name: NonEmptyText = Field(description="Reported project feature or capability name.")
    description: NonEmptyText | None = Field(
        default=None, description="Reported feature scope; distinguish plans from implemented work."
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.UNKNOWN,
        description="Reported implementation status; unknown when not explicitly stated.",
    )


class Project(EvidenceRecord):
    name: NonEmptyText = Field(description="Reported project name.")
    status: ProjectStatus = Field(
        default=ProjectStatus.UNKNOWN,
        description="Reported development status; default unknown, never inferred.",
    )
    description: NonEmptyText | None = Field(
        default=None, description="Reported project scope; distinguish plans from delivered work."
    )
    technologies: list[NonEmptyText] = Field(
        default_factory=list,
        description="Reported technologies, interpreted with the project status.",
    )
    features: list[ProjectFeature] = Field(
        default_factory=list,
        description="Capabilities with independent implementation status, evidence, and review.",
    )
    responsibilities: list[NonEmptyText] = Field(
        default_factory=list,
        description="Reported contribution or planned scope, according to status.",
    )
    achievements: list[NonEmptyText] = Field(
        default_factory=list,
        description="Already achieved outcomes; must be empty for planned work.",
    )
    dates: DateRange | None = Field(default=None, description="Reported project period, if known.")
    links: list[HttpUrl] = Field(
        default_factory=list, description="Relevant project, demo, or GitHub repository references."
    )

    @model_validator(mode="after")
    def validate_project_status(self) -> Self:
        if self.status == ProjectStatus.PLANNED and self.achievements:
            raise ValueError("Planned projects cannot have completed achievements.")
        if (
            self.dates is not None
            and self.dates.is_current is True
            and self.status in (ProjectStatus.COMPLETED, ProjectStatus.PLANNED)
        ):
            raise ValueError("A completed or planned project cannot have an ongoing period.")
        if (
            self.status == ProjectStatus.IN_PROGRESS
            and self.dates is not None
            and (self.dates.end is not None or self.dates.is_current is False)
        ):
            raise ValueError("An in_progress project cannot have an ended period.")
        return self


class Certification(EvidenceRecord):
    name: NonEmptyText = Field(description="Reported certification name.")
    issuer: NonEmptyText | None = Field(default=None, description="Reported issuing organization.")
    issued_on: PartialDate | None = Field(
        default=None, description="Reported issue date, if known."
    )
    expires_on: PartialDate | None = Field(
        default=None, description="Reported expiry date, if known."
    )
    url: HttpUrl | None = Field(default=None, description="Public credential or verification URL.")

    @model_validator(mode="after")
    def validate_validity_dates(self) -> Self:
        DateRange(start=self.issued_on, end=self.expires_on)
        return self


class AwardAchievement(EvidenceRecord):
    title: NonEmptyText = Field(description="Reported award or achievement title.")
    description: NonEmptyText | None = Field(
        default=None, description="Reported achievement details."
    )
    issuer: NonEmptyText | None = Field(
        default=None, description="Awarding organization, if known."
    )
    awarded_on: PartialDate | None = Field(
        default=None, description="Reported award date, if known."
    )
    url: HttpUrl | None = Field(default=None, description="Public supporting URL, if available.")


class SpokenLanguage(EvidenceRecord):
    language: NonEmptyText = Field(description="Reported spoken language name.")
    proficiency: NonEmptyText | None = Field(
        default=None, description="As reported, for example native, fluent, or B2; never inferred."
    )


class CareerPreferences(EvidenceRecord):
    """Manually supplied preferences; entering them does not automatically verify them."""

    target_roles: list[NonEmptyText] = Field(
        default_factory=list, description="Roles explicitly requested by the user."
    )
    preferred_locations: list[NonEmptyText] = Field(
        default_factory=list, description="Locations explicitly preferred by the user."
    )
    work_modes: list[WorkMode] = Field(
        default_factory=list, description="User-selected modes: remote, hybrid, and/or on_site."
    )

    @model_validator(mode="after")
    def validate_manual_sources(self) -> Self:
        if any(source.source_type != SourceType.MANUAL for source in self.sources):
            raise ValueError("Career preferences must use manual source references.")
        return self


class ProfessionalProfile(ProfileModel):
    """Partial professional facts; no root approval flag can verify every nested record."""

    identity: Identity = Field(default_factory=Identity, description="Known identity information.")
    professional_summary: ProfessionalSummary | None = Field(
        default=None, description="Optional professional summary with evidence and review status."
    )
    technical_skills: list[SkillCategory] = Field(
        default_factory=list, description="Technical skills grouped into named categories."
    )
    work_experience: list[WorkExperience] = Field(
        default_factory=list, description="Reported work history; missing entries mean unknown."
    )
    education: list[Education] = Field(
        default_factory=list, description="Reported education records."
    )
    projects: list[Project] = Field(
        default_factory=list,
        description="Projects with reported or unknown development status and evidence.",
    )
    certifications: list[Certification] = Field(
        default_factory=list, description="Reported professional certifications."
    )
    awards: list[AwardAchievement] = Field(
        default_factory=list, description="Reported awards and achievements."
    )
    spoken_languages: list[SpokenLanguage] = Field(
        default_factory=list, description="Languages and explicitly reported proficiency."
    )
    career_preferences: CareerPreferences | None = Field(
        default=None, description="Optional manually supplied career preferences; never inferred."
    )
