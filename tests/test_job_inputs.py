"""Validate user inputs and explicit pairing of URLs with their pasted fallback."""

import argparse
import json

import pytest
from pydantic import ValidationError

from aura.agent.__main__ import load_jobs
from aura.schemas.job import JobInput


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"description": " "},
        {"url": "file:///secret"},
        {"url": "https://user:password@jobs.example.test/a"},
        {"description": "x" * 20_001},
        {"description": "Job", "verified": True},
    ],
)
def test_invalid_or_authoritative_fields_are_rejected(fields):
    with pytest.raises(ValidationError):
        JobInput(**fields)


def test_job_inputs_json_roundtrip_and_optional_fallback():
    job = JobInput(
        label="Developer", url="https://jobs.example.test/python", description="Python required"
    )
    assert JobInput.model_validate_json(job.model_dump_json()) == job
    assert JobInput(description="SQL required").url is None
    assert JobInput(url="https://jobs.example.test/sql").description is None


def test_manifest_preserves_each_jobs_source_pair(tmp_path):
    manifest = tmp_path / "jobs.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "label": "Developer",
                    "url": "https://jobs.example.test/python",
                    "description": "Python required",
                },
                {"label": "Analyst", "description": "SQL required"},
            ]
        ),
        encoding="utf-8",
    )
    jobs = load_jobs(argparse.Namespace(jobs=manifest, job=None, job_url=[]))
    assert len(jobs) == 2 and jobs[0].url is not None and jobs[1].url is None
    assert jobs[0].description == "Python required" and jobs[1].description == "SQL required"


def test_single_url_uses_job_file_as_explicit_fallback(tmp_path):
    pasted = tmp_path / "job.txt"
    pasted.write_text("Python required", encoding="utf-8-sig")
    jobs = load_jobs(
        argparse.Namespace(jobs=None, job=pasted, job_url=["https://jobs.example.test/a"])
    )
    assert jobs[0].url is not None and jobs[0].description == "Python required"


def test_multiple_url_flags_create_separate_inputs():
    jobs = load_jobs(
        argparse.Namespace(
            jobs=None,
            job=None,
            job_url=["https://jobs.example.test/a", "https://jobs.example.test/b"],
        )
    )
    assert len(jobs) == 2 and all(job.description is None for job in jobs)


@pytest.mark.parametrize("contents", ["{}", "[]", "not JSON", '[{"description":""}]'])
def test_invalid_manifests_rejected(tmp_path, contents):
    manifest = tmp_path / "jobs.json"
    manifest.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        load_jobs(argparse.Namespace(jobs=manifest, job=None, job_url=[]))


def test_ambiguous_fallback_pairing_is_rejected_without_reading_files():
    with pytest.raises(ValueError, match="pair"):
        load_jobs(
            argparse.Namespace(
                jobs=None, job=object(), job_url=["https://a.test", "https://b.test"]
            )
        )
