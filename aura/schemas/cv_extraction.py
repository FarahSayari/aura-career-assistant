"""Untrusted Gemini output: professional facts only, without application trust metadata."""

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from aura.schemas.professional_profile import DateRange, NonEmptyText, PartialDate, ProjectStatus


class CvFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CvContact(CvFacts):
    email: NonEmptyText | None = Field(default=None, description="Email exactly as reported.")
    phone: NonEmptyText | None = Field(default=None, description="Phone exactly as reported.")
    links: list[HttpUrl] = Field(
        default_factory=list, description="Explicit professional contact URLs."
    )


class CvIdentity(CvFacts):
    full_name: NonEmptyText | None = Field(default=None, description="Reported full name, or null.")
    professional_title: NonEmptyText | None = Field(
        default=None, description="Reported title, or null."
    )
    location: NonEmptyText | None = Field(default=None, description="Reported location, or null.")
    contact: CvContact | None = Field(
        default=None, description="Optional reported contact details."
    )


class CvSummary(CvFacts):
    text: NonEmptyText = Field(description="Reported professional summary; do not embellish.")


class CvSkill(CvFacts):
    name: NonEmptyText = Field(description="Explicitly reported skill; never inferred from a role.")


class CvSkillCategory(CvFacts):
    name: NonEmptyText = Field(description="Original reported skill category where possible.")
    skills: list[CvSkill] = Field(
        default_factory=list, description="Reported skills in this category."
    )


class CvExperience(CvFacts):
    organization: NonEmptyText | None = Field(
        default=None, description="Reported employer or client."
    )
    role: NonEmptyText | None = Field(default=None, description="Reported position, or null.")
    location: NonEmptyText | None = Field(
        default=None, description="Reported work location, or null."
    )
    dates: DateRange | None = Field(
        default=None, description="Reported dates with original precision."
    )
    responsibilities: list[NonEmptyText] = Field(
        default_factory=list, description="Reported duties."
    )
    achievements: list[NonEmptyText] = Field(
        default_factory=list, description="Reported outcomes only."
    )


class CvEducation(CvFacts):
    institution: NonEmptyText | None = Field(default=None, description="Reported institution.")
    degree: NonEmptyText | None = Field(default=None, description="Reported qualification.")
    specialization: NonEmptyText | None = Field(
        default=None, description="Reported field of study."
    )
    dates: DateRange | None = Field(
        default=None, description="Reported dates; missing parts stay null."
    )


class CvProjectFeature(CvFacts):
    name: NonEmptyText = Field(description="Reported project feature or capability.")
    description: NonEmptyText | None = Field(default=None, description="Reported feature scope.")
    status: ProjectStatus = Field(
        default=ProjectStatus.UNKNOWN,
        description="Only an explicitly reported status; otherwise unknown.",
    )


class CvProject(CvFacts):
    name: NonEmptyText = Field(description="Reported project name; do not duplicate projects.")
    status: ProjectStatus = Field(
        default=ProjectStatus.UNKNOWN,
        description="Only an explicitly reported status; otherwise unknown.",
    )
    description: NonEmptyText | None = Field(default=None, description="Reported project scope.")
    technologies: list[NonEmptyText] = Field(
        default_factory=list, description="Reported technologies."
    )
    features: list[CvProjectFeature] = Field(
        default_factory=list, description="Reported feature states."
    )
    responsibilities: list[NonEmptyText] = Field(
        default_factory=list, description="Reported contribution."
    )
    achievements: list[NonEmptyText] = Field(
        default_factory=list, description="Already achieved outcomes."
    )
    dates: DateRange | None = Field(default=None, description="Reported project dates, if known.")
    links: list[HttpUrl] = Field(
        default_factory=list, description="Explicit project/demo/repository URLs."
    )


class CvCertification(CvFacts):
    name: NonEmptyText = Field(description="Reported certification name.")
    issuer: NonEmptyText | None = Field(default=None, description="Reported issuer, if known.")
    issued_on: PartialDate | None = Field(
        default=None, description="Reported issue date, if known."
    )
    expires_on: PartialDate | None = Field(
        default=None, description="Reported expiry date, if known."
    )
    url: HttpUrl | None = Field(default=None, description="Explicit credential URL, if present.")


class CvAward(CvFacts):
    title: NonEmptyText = Field(description="Reported award/achievement title.")
    description: NonEmptyText | None = Field(
        default=None, description="Reported achievement details."
    )
    issuer: NonEmptyText | None = Field(default=None, description="Reported awarding organization.")
    awarded_on: PartialDate | None = Field(
        default=None, description="Reported award date, if known."
    )
    url: HttpUrl | None = Field(default=None, description="Explicit supporting URL, if present.")


class CvLanguage(CvFacts):
    language: NonEmptyText = Field(description="Reported language name.")
    proficiency: NonEmptyText | None = Field(
        default=None, description="Reported proficiency, never inferred."
    )


class CvExtraction(CvFacts):
    """This schema deliberately cannot express sources, verification, or preferences."""

    identity: CvIdentity = Field(default_factory=CvIdentity)
    professional_summary: CvSummary | None = None
    technical_skills: list[CvSkillCategory] = Field(default_factory=list)
    work_experience: list[CvExperience] = Field(default_factory=list)
    education: list[CvEducation] = Field(default_factory=list)
    projects: list[CvProject] = Field(default_factory=list)
    certifications: list[CvCertification] = Field(default_factory=list)
    awards: list[CvAward] = Field(default_factory=list)
    spoken_languages: list[CvLanguage] = Field(default_factory=list)
