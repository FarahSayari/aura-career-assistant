"""User-supplied job inputs; labels identify documents, not verified professional facts."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

MAX_JOBS = 5
MAX_JOB_CHARACTERS = 20_000
MAX_TOTAL_JOB_CHARACTERS = 40_000


class JobInput(BaseModel):
    """One supplied opportunity, with optional pasted text to use if its URL fails."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str | None = Field(default=None, max_length=120, description="User's document label.")
    url: HttpUrl | None = Field(default=None, description="Public posting URL, not a search query.")
    description: str | None = Field(
        default=None,
        max_length=MAX_JOB_CHARACTERS,
        description="Pasted posting, or fallback text for an inaccessible URL.",
    )

    @field_validator("label", "description")
    @classmethod
    def nonblank_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Use nonblank text or omit the field.")
        return value.strip() if value is not None else None

    @field_validator("url")
    @classmethod
    def no_url_credentials(cls, value: HttpUrl | None) -> HttpUrl | None:
        if value is not None and (value.username is not None or value.password is not None):
            raise ValueError("Job URLs must not contain credentials.")
        return value

    @model_validator(mode="after")
    def require_source(self) -> Self:
        if self.url is None and self.description is None:
            raise ValueError("Supply a job URL or a pasted description.")
        return self
