#!/usr/bin/env python3
"""Run reproducible project checks and write a redacted JSON report."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import venv
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = ("offline", "browser", "mcp", "live", "dependencies", "packaging", "all")


@dataclass(frozen=True)
class Check:
    """One independently rerunnable check."""

    id: str
    mode: str
    command: tuple[str, ...]
    modules: tuple[str, ...] = ()
    optional_setting: str | None = None


@dataclass
class Result:
    """Outcome and diagnostics without environment secrets."""

    id: str
    status: str
    seconds: float = 0
    returncode: int | None = None
    output: str = ""


def redact(text: str) -> str:
    """Remove URL credentials and configured secret values from diagnostics."""
    text = re.sub(r"(\b[a-zA-Z][\w+.-]*://)[^\s/@]+@", r"\1[redacted]@", text)
    secrets = [
        value
        for key, value in os.environ.items()
        if re.search(r"(?:PASSWORD|TOKEN|SECRET|API_KEY|ACCESS_KEY)", key, re.I) and value
    ]
    for value in sorted(secrets, key=len, reverse=True):
        text = text.replace(value, "[redacted]")
    return text


def checks(dist_dir: Path) -> list[Check]:
    """List checks in dependency order without launching any tools."""
    python = sys.executable
    test = (python, "-m", "pytest", "-q")
    items = [
        Check("lint", "offline", (python, "-m", "ruff", "check", "."), ("ruff",)),
        Check("format", "offline", (python, "-m", "ruff", "format", "--check", "."), ("ruff",)),
        Check("types", "offline", (python, "-m", "pyright", "--pythonpath", python), ("pyright",)),
        Check("unit", "offline", test + ("-m", "not live and not browser"), ("pytest",)),
        Check("pip-check", "dependencies", (python, "-m", "pip", "check"), ("pip",)),
        Check(
            "mcp", "mcp", test + ("-m", "mcp", "tests/test_mcp_protocol.py"), ("pytest", "fastmcp")
        ),
        Check(
            "browser",
            "browser",
            test + ("-m", "browser", "tests/test_browser_live.py"),
            ("pytest", "playwright"),
        ),
        Check(
            "outdated",
            "dependencies",
            (
                python,
                "-m",
                "pip",
                "--no-cache-dir",
                "list",
                "--outdated",
                "--format=json",
                "--disable-pip-version-check",
                "--retries",
                "0",
                "--timeout",
                "15",
            ),
            ("pip",),
        ),
        Check(
            "audit",
            "dependencies",
            (
                python,
                "-m",
                "pip_audit",
                "--local",
                "--cache-dir",
                str(dist_dir.parent / "audit-cache"),
                "--format=json",
                "--desc=off",
                "--progress-spinner=off",
                "--timeout",
                "15",
            ),
            ("pip_audit",),
        ),
        Check("build", "packaging", (python, "-m", "build", "--outdir", str(dist_dir)), ("build",)),
    ]
    for extra in ("base", "browser", "all"):
        items.append(
            Check(
                f"install-{extra}",
                "packaging",
                (
                    python,
                    str(Path(__file__).resolve()),
                    "--install-extra",
                    extra,
                    "--dist-dir",
                    str(dist_dir),
                ),
                ("pip",),
            )
        )
    for provider in (
        "wikipedia",
        "duckduckgo",
        "stackexchange",
        "wikidata",
        "hackernews",
        "arxiv",
        "pubmed",
        "github",
        "mdn",
        "searxng",
    ):
        setting = "SOLOCRAWL_SEARXNG_URL" if provider == "searxng" else None
        items.append(
            Check(
                f"search-{provider}",
                "live",
                test
                + (
                    "-m",
                    "live",
                    f"tests/test_smoke_live.py::test_search_provider_live[{provider}]",
                ),
                ("pytest",),
                setting,
            )
        )
    for ecosystem in (
        "pypi",
        "npm",
        "packagist",
        "crates",
        "nuget",
        "maven",
        "rubygems",
        "go",
        "pub",
        "swift",
    ):
        items.append(
            Check(
                f"package-{ecosystem}",
                "live",
                test
                + (
                    "-m",
                    "live",
                    f"tests/test_smoke_live.py::test_package_provider_live[{ecosystem}]",
                ),
                ("pytest",),
            )
        )
    for name in ("federated_search", "fetch", "research", "batch"):
        items.append(
            Check(
                f"live-{name}",
                "live",
                test
                + (
                    "-m",
                    "live",
                    f"tests/test_smoke_live.py::test_{name}_live",
                ),
                ("pytest",),
            )
        )
    return items


def run(check: Check, *, timeout: int, explicit: bool = False) -> Result:
    """Execute one check, distinguishing failures from missing prerequisites."""
    if check.optional_setting and not os.environ.get(check.optional_setting):
        return Result(
            check.id,
            "blocked" if explicit else "skip",
            output=(f"Set {check.optional_setting} to test this optional provider."),
        )
    missing = [module for module in check.modules if importlib.util.find_spec(module) is None]
    if missing:
        return Result(check.id, "blocked", output=f"Missing modules: {', '.join(missing)}")
    if check.id == "browser":
        # Presence of the Python package does not prove Chromium has been installed.
        try:
            sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright
            with sync_playwright() as playwright:
                if not Path(playwright.chromium.executable_path).is_file():
                    return Result(
                        check.id, "blocked", output="Run: python -m playwright install chromium"
                    )
        except Exception as exc:
            return Result(check.id, "blocked", output=redact(str(exc)))
    start = time.monotonic()
    env = dict(os.environ)
    env["FASTMCP_MCP_CAMELCASE_COMPAT"] = "false"
    try:
        completed = subprocess.run(
            check.command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Result(check.id, "blocked", time.monotonic() - start, output=redact(str(exc)))
    output = redact(completed.stdout + completed.stderr)
    status = "pass" if completed.returncode == 0 else "fail"
    if completed.returncode == 5 and "pytest" in check.command:
        status = "blocked"  # no tests collected must never count as a successful verification
    network_problem = re.search(
        r"ConnectionError|Connection refused|Failed to establish|NameResolutionError|"
        r"Temporary failure in name resolution|CERTIFICATE_VERIFY_FAILED|Domain not in allowlist|"
        r"ConnectTimeout|ReadTimeout|could not fetch|No matching distribution found|"
        r"PermissionError|Operation not permitted|Permission denied",
        output,
        re.I,
    )
    if check.mode in {"dependencies", "packaging"} and network_problem:
        status = "blocked"
    # pip can report success after a failed per-package index query.
    if check.id == "outdated" and ("WARNING:" in completed.stderr or "ERROR:" in completed.stderr):
        status = "blocked"
    return Result(
        check.id,
        status,
        round(time.monotonic() - start, 2),
        completed.returncode,
        output if check.id in {"audit", "outdated"} else output[-100_000:],
    )


def clean_install(extra: str, dist_dir: Path) -> int:
    """Install the built wheel in a new environment and exercise installed entry points."""
    wheels = sorted(dist_dir.glob("solocrawl-*.whl"))
    if not wheels:
        print("Missing built wheel; run the build check first.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="solocrawl-install-") as directory:
        root = Path(directory)
        venv.EnvBuilder(with_pip=True).create(root)
        binaries = root / ("Scripts" if os.name == "nt" else "bin")
        python = str(binaries / ("python.exe" if os.name == "nt" else "python"))
        requirement = str(wheels[-1].resolve()) + (f"[{extra}]" if extra != "base" else "")
        commands = [
            [
                python,
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--disable-pip-version-check",
                "--retries",
                "0",
                "--timeout",
                "15",
                requirement,
            ],
            [python, "-m", "pip", "check"],
            [str(binaries / ("solocrawl.exe" if os.name == "nt" else "solocrawl")), "--help"],
            [str(binaries / ("solocrawl.exe" if os.name == "nt" else "solocrawl")), "providers"],
            [
                python,
                "-c",
                "from solocrawl.mcp.server import create_server; "
                "assert create_server().name == 'SoloCrawl'",
            ],
        ]
        if extra != "base":
            commands.append(
                [
                    python,
                    "-c",
                    "from solocrawl.core.fetch.browser import "
                    "playwright_available; assert playwright_available()",
                ]
            )
        env = dict(os.environ)
        env["PYTHON_DOTENV_DISABLED"] = "1"
        env["FASTMCP_MCP_CAMELCASE_COMPAT"] = "false"
        for command in commands:
            completed = subprocess.run(command, cwd=root, env=env, check=False)
            if completed.returncode:
                return completed.returncode
        print(f"Clean {extra} install and entry points passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run selected checks and persist a report suitable for sharing as feedback."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="offline")
    parser.add_argument(
        "--check", action="append", default=[], help="Run a specific ID; repeatable"
    )
    parser.add_argument(
        "--list", action="store_true", help="List available IDs without running checks"
    )
    parser.add_argument("--timeout", type=int, default=300, help="Seconds allowed per check")
    parser.add_argument(
        "--json", type=Path, help="Report destination (default: artifacts/verification)"
    )
    parser.add_argument(
        "--install-extra", choices=("base", "browser", "all"), help=argparse.SUPPRESS
    )
    parser.add_argument("--dist-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.install_extra:
        if args.dist_dir is None:
            parser.error("--install-extra requires --dist-dir")
        return clean_install(args.install_extra, args.dist_dir)
    started = datetime.now(UTC)
    run_dir = ROOT / "artifacts" / "verification" / started.strftime("%Y%m%dT%H%M%S%fZ")
    dist_dir = args.dist_dir or run_dir / "dist"
    inventory = checks(dist_dir)
    if args.list:
        for check in inventory:
            print(f"{check.id:24} {check.mode}")
        return 0
    unknown = set(args.check) - {check.id for check in inventory}
    if unknown:
        parser.error(f"unknown check IDs: {', '.join(sorted(unknown))}")
    selected = [
        check
        for check in inventory
        if (
            check.id in args.check
            if args.check
            else args.mode == "all"
            or check.mode == args.mode
            or (args.mode == "offline" and check.id == "pip-check")
        )
    ]
    # A fresh wheel is needed even when an install ID is requested on its own.
    if any(check.id.startswith("install-") for check in selected) and not any(
        check.id == "build" for check in selected
    ):
        selected.insert(0, next(check for check in inventory if check.id == "build"))
    results: list[Result] = []
    for check in selected:
        print(f"RUN  {check.id}", flush=True)
        if check.id.startswith("install-") and any(
            result.id == "build" and result.status != "pass" for result in results
        ):
            result = Result(check.id, "blocked", output="Build did not pass.")
        else:
            result = run(check, timeout=args.timeout, explicit=check.id in args.check)
        result.output = redact(result.output)
        results.append(result)
        print(f"{result.status.upper():7} {result.id} ({result.seconds:.2f}s)", flush=True)
        if result.status in {"fail", "blocked"}:
            print(result.output[-2000:].strip(), flush=True)
    versions: dict[str, str] = {}
    metadata_warnings: list[str] = []
    for distribution in importlib.metadata.distributions():
        metadata = distribution.metadata
        name = metadata.get("Name")
        version = metadata.get("Version")
        if not name or not version:
            warning = "Skipped installed distribution with missing Name or Version metadata."
            metadata_warnings.append(warning)
            print(f"WARN {warning}", flush=True)
            continue
        versions[name] = version
    report = {
        "schema_version": 1,
        "started_at": started.isoformat(),
        "mode": args.mode,
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "versions": dict(sorted(versions.items())),
        "metadata_warnings": metadata_warnings,
        "results": [asdict(result) for result in results],
    }
    destination = args.json or run_dir / "report.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {destination}")
    if any(result.status == "fail" for result in results):
        return 1
    return 2 if any(result.status == "blocked" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
