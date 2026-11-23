"""Convert untrusted extraction facts into a new, entirely unverified profile."""

from pydantic import BaseModel

from aura.schemas.cv_extraction import CvExtraction
from aura.schemas.professional_profile import (
    EvidenceRecord,
    ProfessionalProfile,
    SourceReference,
    SourceType,
    VerificationStatus,
)


def to_professional_profile(
    extraction: CvExtraction, *, document_name: str, page_count: int
) -> ProfessionalProfile:
    """Attach application-owned document provenance, without modifying any existing profile."""
    if page_count < 1:
        raise ValueError("A CV source must contain at least one page.")
    source = SourceReference(
        source_type=SourceType.CV,
        reference=document_name,
        locator=f"Document text, pages 1–{page_count}; page-level attribution not resolved",
    )
    profile = ProfessionalProfile.model_validate(extraction.model_dump(mode="json"))

    def attach_provenance(value: object) -> None:
        if isinstance(value, EvidenceRecord):
            value.sources = [source.model_copy(deep=True)]
            value.verification_status = VerificationStatus.UNVERIFIED
        if isinstance(value, BaseModel):
            for name in type(value).model_fields:
                if name not in {"sources", "verification_status"}:
                    attach_provenance(getattr(value, name))
        elif isinstance(value, list):
            for item in value:
                attach_provenance(item)

    attach_provenance(profile)
    return profile
