"""Exercise the local runner without any model or network call."""

import json
from unittest.mock import MagicMock

import pytest

from aura.agent import __main__ as runner


def test_runner_needs_explicit_consent_before_reading_files(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aura.agent", "--cv", "missing.pdf", "--job", "missing.txt"])
    model = MagicMock()
    monkeypatch.setattr(runner, "CareerAssistant", model)
    with pytest.raises(SystemExit) as failure:
        runner.main()
    assert failure.value.code == 2
    assert "--allow-external-processing" in capsys.readouterr().err
    model.assert_not_called()


def test_runner_handles_conversation_reset_and_closes_resources(monkeypatch, tmp_path, make_pdf):
    cv = tmp_path / "synthetic.pdf"
    job = tmp_path / "synthetic-job.txt"
    cv.write_bytes(make_pdf(["Synthetic Python CV"]))
    job.write_text("Python required", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        ["aura.agent", "--cv", str(cv), "--job", str(job), "--allow-external-processing"],
    )
    questions = iter(["Compare", "Why?", "/reset", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _: next(questions))
    constructor = MagicMock()
    monkeypatch.setattr(runner, "CareerAssistant", constructor)
    runner.main()
    agent = constructor.return_value
    assert constructor.call_args.args == (cv.read_bytes(), "Python required")
    assert constructor.call_args.kwargs["consent_to_send"] is True
    assert [call.args[0] for call in agent.ask.call_args_list] == ["Compare", "Why?"]
    agent.reset.assert_called_once()
    agent.close.assert_called_once()


def test_invalid_configuration_has_no_raw_settings_dump(monkeypatch, capsys):
    monkeypatch.setenv("AURA_AGENT_MAX_MODEL_CALLS", "SYNTHETIC_PRIVATE_INVALID_VALUE")
    monkeypatch.setattr(
        "sys.argv",
        ["aura.agent", "--cv", "unused.pdf", "--job", "unused.txt", "--allow-external-processing"],
    )
    with pytest.raises(SystemExit) as failure:
        runner.main()
    assert failure.value.code == 1
    error = capsys.readouterr().err
    assert "Invalid Aura settings" in error
    assert "PRIVATE_INVALID" not in error


def test_runner_passes_manifest_jobs_and_does_not_fetch_on_start(monkeypatch, tmp_path, make_pdf):
    cv = tmp_path / "synthetic.pdf"
    cv.write_bytes(make_pdf(["Synthetic Python CV"]))
    manifest = tmp_path / "jobs.json"
    manifest.write_text(
        json.dumps(
            [
                {"url": "https://jobs.example.test/python", "description": "Python fallback"},
                {"description": "SQL required"},
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["aura.agent", "--cv", str(cv), "--jobs", str(manifest), "--allow-external-processing"],
    )
    monkeypatch.setattr("builtins.input", lambda _: "/quit")
    constructor = MagicMock()
    monkeypatch.setattr(runner, "CareerAssistant", constructor)
    runner.main()
    jobs = constructor.call_args.kwargs["jobs"]
    assert len(jobs) == 2 and jobs[0].description == "Python fallback"
    constructor.return_value.ask.assert_not_called()
    constructor.return_value.close.assert_called_once()
