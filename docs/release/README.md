# Release and packaging

SoloCrawl uses Hatchling with the `src/solocrawl` package layout. Python 3.14+ is required. The base
installation provides `solocrawl` and `solocrawl-mcp`; `browser` adds Playwright, and `all` includes
that extra. Browser binaries are installed separately with `python -m playwright install chromium`.

Run [the release checklist](CHECKLIST.md), including the
[verification runner](../verification.md), before creating a release. Building or testing never
publishes a package or creates a tag automatically. Publishing and tagging are separate deliberate
release actions.

```bash
python -m pip install -e ".[dev]"
python scripts/verify_project.py --mode packaging
```

The packaging report points to the run's wheel and source distribution under
`artifacts/verification/<run>/dist/`. Clean install checks use temporary environments outside the
checkout so editable imports cannot hide missing wheel contents.

Review the version in `pyproject.toml` when preparing an actual release. The package reads installed
metadata and has a matching fallback in `src/solocrawl/__init__.py` for an uninstalled checkout.
Reinstall the editable package after a version bump so installed metadata matches the checkout.

The prepared [1.1.0 release notes](1.1.0.md) can be used with GitHub's release form or
`gh release create --notes-file docs/release/1.1.0.md`. Release preparation alone does not publish
the package to GitHub or PyPI.
