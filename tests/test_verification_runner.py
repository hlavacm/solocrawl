"""The verification report must distinguish unavailable checks and protect secrets."""

from __future__ import annotations

import importlib.metadata
import json
import subprocess
import sys

import pytest
from scripts import verify_project as verification


@pytest.mark.parametrize("metadata", ["", "Name: incomplete\n", "Version: 1.0\n"])
def test_report_handles_incomplete_distribution_metadata(tmp_path, monkeypatch, metadata):
    broken = tmp_path / "broken.dist-info"
    broken.mkdir()
    (broken / "METADATA").write_text(metadata)
    valid = tmp_path / "valid.dist-info"
    valid.mkdir()
    (valid / "METADATA").write_text("Name: valid\nVersion: 1.0\n")
    monkeypatch.setattr(
        verification.importlib.metadata,
        "distributions",
        lambda: [
            importlib.metadata.PathDistribution(broken),
            importlib.metadata.PathDistribution(valid),
        ],
    )
    monkeypatch.setattr(
        verification, "run", lambda check, **kwargs: verification.Result(check.id, "pass")
    )
    report = tmp_path / "report.json"
    assert verification.main(["--check", "lint", "--json", str(report)]) == 0
    parsed = json.loads(report.read_text())
    assert parsed["versions"] == {"valid": "1.0"}
    assert len(parsed["metadata_warnings"]) == 1


def test_report_is_valid_json_with_secret_characters(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOLOCRAWL_PROXY_PASSWORD", 'p"ass')
    monkeypatch.setattr(
        verification,
        "run",
        lambda check, **kwargs: verification.Result(
            check.id,
            "fail",
            output='Request failed with p"ass',
        ),
    )
    report = tmp_path / "report.json"
    assert verification.main(["--check", "lint", "--json", str(report)]) == 1
    parsed = json.loads(report.read_text())
    assert parsed["schema_version"] == 1
    assert 'p"ass' not in parsed["results"][0]["output"]


def test_missing_tool_is_blocked():
    check = verification.Check(
        "missing",
        "offline",
        (sys.executable, "-c", "pass"),
        ("solocrawl_nonexistent_verification_tool",),
    )
    result = verification.run(check, timeout=10)
    assert result.status == "blocked"
    assert result.returncode is None


def test_index_query_warning_cannot_pass(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        verification.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "[]", "WARNING: index unavailable"
        ),
    )
    check = verification.Check("outdated", "dependencies", ("python", "-m", "pip"))
    assert verification.run(check, timeout=10).status == "blocked"


@pytest.mark.parametrize("check_id", ["audit", "outdated"])
def test_dependency_json_is_not_truncated(monkeypatch: pytest.MonkeyPatch, check_id: str):
    payload = {"dependencies": [{"description": "details " * 15_000}]}
    monkeypatch.setattr(
        verification.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, json.dumps(payload), ""),
    )
    check = verification.Check(check_id, "dependencies", (sys.executable, "-m", "pip"))
    result = verification.run(check, timeout=10)
    assert json.loads(result.output) == payload


def test_url_credentials_are_redacted():
    assert verification.redact("failed https://name:password@proxy.test/") == (
        "failed https://[redacted]@proxy.test/"
    )
