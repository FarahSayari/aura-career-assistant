"""Explicit local runner for P1.1; the Streamlit conversation comes in P1.3."""

import argparse
from pathlib import Path

from pydantic import ValidationError

from aura.agent import CareerAgentError, CareerAssistant
from aura.core.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aura P1.1: one PDF, one pasted-text job, and chat."
    )
    parser.add_argument("--cv", type=Path, required=True, help="Local PDF you explicitly select.")
    parser.add_argument(
        "--job", type=Path, required=True, help="UTF-8 file containing one job posting."
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
        if args.job.stat().st_size > 80_000:
            parser.error("The job description file is too large.")
        agent = CareerAssistant(
            args.cv.read_bytes(),
            args.job.read_text(encoding="utf-8"),
            settings=settings,
            consent_to_send=True,
        )
        print("Aura — unverified advice. pdfplumber may interleave CV columns. Type /quit to exit.")
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
        parser.exit(1, "Invalid Aura settings. Check the values in your local configuration.\n")
    except (OSError, UnicodeError):
        parser.exit(1, "Could not read the selected input files. Check paths and UTF-8 encoding.\n")
    except (EOFError, KeyboardInterrupt):
        print("\nConversation ended.")
    finally:
        if agent is not None:
            agent.close()


if __name__ == "__main__":
    main()
