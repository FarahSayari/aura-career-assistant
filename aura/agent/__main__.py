"""Explicit local runner for PDF/job intake and chat; Streamlit chat comes in P1.3."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from aura.agent import CareerAgentError, CareerAssistant
from aura.core.config import Settings
from aura.schemas.job import MAX_JOBS, JobInput


def load_jobs(args: argparse.Namespace) -> list[JobInput]:
    """Read only explicitly selected files; a manifest pairs each URL with its fallback."""
    if args.jobs is not None:
        if args.job is not None or args.job_url:
            raise ValueError("Use --jobs alone, or --job/--job-url inputs.")
        if args.jobs.stat().st_size > 200_000:
            raise ValueError("The jobs manifest is too large.")
        records = json.loads(args.jobs.read_text(encoding="utf-8-sig"))
        if not isinstance(records, list) or not 1 <= len(records) <= MAX_JOBS:
            raise ValueError("The jobs manifest must be a list of one to five jobs.")
        return [JobInput.model_validate(record) for record in records]
    if len(args.job_url) > MAX_JOBS:
        raise ValueError("Supply at most five job URLs.")
    if args.job is not None and len(args.job_url) > 1:
        raise ValueError("Use --jobs to pair pasted fallbacks with multiple URLs.")
    pasted = None
    if args.job is not None:
        if args.job.stat().st_size > 80_000:
            raise ValueError("The job description file is too large.")
        pasted = args.job.read_text(encoding="utf-8-sig")
    if args.job_url:
        return [JobInput(url=url, description=pasted) for url in args.job_url]
    if pasted is not None:
        return [JobInput(description=pasted)]
    raise ValueError("Supply --job, --job-url, or --jobs.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aura: one PDF, supplied job URLs/pasted descriptions, and career chat."
    )
    parser.add_argument("--cv", type=Path, required=True, help="Local PDF you explicitly select.")
    parser.add_argument(
        "--job", type=Path, help="UTF-8 pasted job; optional fallback for a single --job-url."
    )
    parser.add_argument(
        "--job-url", action="append", default=[], help="Public job URL; repeat up to 5 times."
    )
    parser.add_argument(
        "--jobs", type=Path, help="UTF-8 JSON list of jobs with URLs/pasted fallbacks."
    )
    parser.add_argument(
        "--allow-external-processing",
        action="store_true",
        help="Allow sending CV/job text and conversation to Gemini; provider terms apply.",
    )
    args = parser.parse_args()
    if not args.allow_external_processing:
        parser.error(
            "External processing requires --allow-external-processing. Use synthetic data."
        )
    agent = None
    try:
        settings = Settings()
        # Check lengths before loading files, independently of the service's checks.
        if args.cv.stat().st_size > settings.pdf_max_size_mb * 1024 * 1024:
            parser.error("The PDF exceeds the configured size limit.")
        jobs = load_jobs(args)
        # Retain the original one-pasted-job constructor path for existing callers.
        if args.job is not None and not args.job_url and args.jobs is None:
            agent = CareerAssistant(
                args.cv.read_bytes(), jobs[0].description, settings=settings, consent_to_send=True
            )
        else:
            agent = CareerAssistant(
                args.cv.read_bytes(), jobs=jobs, settings=settings, consent_to_send=True
            )
        print("Aura — unverified advice. pdfplumber may interleave CV columns. Type /quit to exit.")
        print("Supplied jobs:", ", ".join(f"job_{i}" for i in range(1, len(jobs) + 1)))
        print(
            "URLs are fetched on the first job-tool call. Failed pages need pasted fallback text."
        )
        print("Type /reset to clear conversation history while retaining the same input documents.")
        while True:
            question = input("You: ").strip()
            if question == "/quit":
                break
            if question == "/reset":
                agent.reset()
                print("Conversation reset.")
                continue
            if not question:
                continue
            try:
                print("Aura:", agent.ask(question))
            except CareerAgentError as error:
                print(error)
    except CareerAgentError as error:
        parser.exit(1, f"{error}\n")
    except ValidationError:
        parser.exit(1, "Invalid Aura settings or job inputs. Check configuration and job fields.\n")
    except ValueError:
        parser.exit(1, "Invalid job inputs. Supply one to five URLs/descriptions; check --help.\n")
    except (OSError, UnicodeError):
        parser.exit(1, "Could not read the selected input files. Check paths and UTF-8 encoding.\n")
    except (EOFError, KeyboardInterrupt):
        print("\nConversation ended.")
    finally:
        if agent is not None:
            agent.close()


if __name__ == "__main__":
    main()
