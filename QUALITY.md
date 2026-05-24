# Quality Standard — opencode-tools

This document defines the quality bar for every tool in this repository.
All contributions and releases must meet these criteria.

## 1. Zero External Dependencies

Every `.py` tool uses **only Python standard library** modules.
No `pip install` required beyond OpenCode itself.

| Allowed | Forbidden |
|---------|-----------|
| `os`, `sys`, `re`, `json`, `subprocess` | `requests`, `click`, `typer`, `rich` |
| `ast`, `hashlib`, `collections` | `numpy`, `pandas`, `pydantic` |
| `unittest` (test files only) | `pytest` (optional, not required) |

Exception: `ruff`, `mypy`, `pytest`, `prettier` may be called as external
binaries by `check`, `fmt`, `lint`, `health` — but never imported as modules.

## 2. Static Type Checking

Every `.py` tool must pass `mypy` with zero errors:

```bash
mypy *.py
```

- Function signatures must have full type annotations (return types + parameters)
- Use `from __future__ import annotations` for forward references
- Use `Any` / `dict[str, Any]` / `list[dict[str, Any]]` for dynamic structures
- Prefer `Optional[str]` over `str | None` in public APIs for 3.10 compat

## 3. Code Formatting

All `.py` files must pass `ruff format --check`:

```bash
ruff format --check .
```

- 88 character line width (ruff default)
- No unused imports
- No trailing whitespace
- UTF-8 encoding with `errors="replace"` for cross-platform safety

## 4. Test Coverage

### Unit Tests
Each tool must have a corresponding `test_<tool>.py` file with:

- CLI arg handling tests (`--version`, `--help`, flags)
- Edge case tests (empty input, missing files, unicode, binary)
- Error handling tests (invalid args, missing directories)
- JSON output format validation where applicable

### Smoke Tests
`smoke_test.py` must verify every tool against its own codebase:

- Each tool: `--version` returns correct version string
- Each tool: `--help` or `-h` returns usage text
- Each tool produces expected output on the repository itself

### CI Gate
All tests must pass on **3 OS × 3 Python versions**:

- Windows (latest), Linux (ubuntu-latest), macOS (latest)
- Python 3.10, 3.11, 3.12+
- `python -m pytest -q --tb=short` — exit code 0 required

## 5. Performance

| Metric | Threshold |
|--------|-----------|
| Cold start (import + parse) | < 200ms |
| `graph` on monorepo (120 files) | < 0.5s |
| `search` on 50k lines | < 0.3s |
| `impact` on monorepo | < 0.2s |
| File size limit | Skip > 50MB (OOM guard) |

## 6. Cross-Platform

Every tool must work on:

- **Windows** (PowerShell 5.1+ and cmd)
- **Linux** (bash, glibc-based distros)
- **macOS** (zsh)

No platform-specific code paths. Use `os.sep`, `os.linesep`, and
`encoding="utf-8", errors="replace"` for all file I/O.

## 7. `.ts` Plugin Wrapper

Every tool must have a matching `.ts` file in the OpenCode plugin format:

```typescript
tool({
  description: "...",
  args: { command: z.string().describe("...") },
  async execute({ command }, ctx) {
    // spawnSync(detectPython(), [findToolPy("tool.py", cwd), ...args])
  },
})
```

The wrapper must:
- Use `detectPython()` for Python discovery
- Use `findToolPy()` for tool path resolution
- Handle errors gracefully with descriptive messages
- Have a 180-second timeout for long-running tools

## 8. Installer Compatibility

Every tool must be listed in:

- `pyproject.toml` — `console_scripts` entry point + `py-modules`
- `package.json` — `files` array
- `install.sh` — `TOOLS` variable
- `install.ps1` — `$Tools` array
- `install.bat` — `TOOLS` variable
- `.github/workflows/ci.yml` — `tools` list + smoke test step

## 9. Documentation

Every tool must have:

- Docstring with usage examples (1-3 lines per option)
- Entry in `README.md` "All Tools" table
- Entry in `CHANGELOG.md` under the release version
- Consistent `--version` and `-h` / `--help` flags

## 10. Release Checklist

```markdown
[ ] All unit tests pass (pytest -q --tb=short)
[ ] All smoke tests pass (python smoke_test.py)
[ ] mypy clean on all .py files
[ ] ruff format --check passes
[ ] CI green on all 3 OS × 3 Python versions
[ ] CHANGELOG.md updated with new version
[ ] README badges reflect new version
[ ] common.py VERSION bumped
[ ] pyproject.toml version bumped
[ ] package.json version bumped
[ ] Tag created and pushed (git tag vX.Y.Z)
[ ] GitHub Release created with release notes
```

---

*Last updated: 2026-05-24 — v0.5.1*
