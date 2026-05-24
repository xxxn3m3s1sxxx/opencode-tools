# Changelog

## [0.5.3] — 2026-05-24

### Fixed
- **ghost**: False positives in Python — `ref_count - def_count` subtraction made every
  single-use symbol look unused. Also broadened attribute tracking from only `self.method()`
  to all attribute loads, catching `instance.method()` patterns.
- **trace/calltrace**: C++ symbols returned empty chains. Added `_find_enclosing_function_cpp()`
  (brace-matching) for caller detection, and `_cpp_find_callees()` in impact.py for forward chains.
- **tags**: `--stats` timed out on large C++ projects. Added `--max-files N` (default 10000)
  to cap file walk. Use `--max-files 0` for unlimited.

## [0.5.2] — 2026-05-24

### Changed
- Restructured repo: `.py` engines → `src/`, `.ts` plugins → `plugins/`, tests → `tests/`
- Updated all paths in CI, installers, package.json, pyproject.toml

### Fixed
- `pyproject.toml` now uses `package-dir = {"" = "src"}` for setuptools discovery
- `test_regression.py` and `stress_tools.py` create temp files in OS tempdir instead of repo root
- `.gitignore` covers `tmp*.py`, `.opencode/plugins/`, `.opencode/snapshots/`

## [0.5.1] — 2026-05-24

### Added
- `check.py` — Pre-commit gate: lint → mypy → tests, exit 0 only if all pass
- `audit.py` — Secret scanner: API keys, passwords, tokens, private keys
- `fmt.py` — Format runner: ruff format + optional prettier
- `churn.py` — Git churn analysis: files with most changes over time
- `report.py` — Combined health report: check + audit + churn + fmt + health
- `ghost.py` — Dead code finder: unused functions, classes, imports

### Fixed
- `trace.ts` renamed to `calltrace.ts` for consistency with `calltrace.py`
- Installer `.ts` mapping for `trace` → `calltrace` in all 3 installers
- `common.py` added to all installers as shared dependency
- `test_installers.py` — updated expected file lists (20 tools)
- `test_trace.py` — docstring + argv cleanup
- CI version assertion bumped to 0.5.1

### Changed
- 6 new `.ts` plugin wrappers + OpenCode integration
- README updated to 19 tools, 360+ tests badge
- All 3 installers now install 20 plugins + common.py

## [0.5.0] — 2026-05-23

### Added
- `health.py` — Project health summary: pytest, mypy, ruff, code metrics
- `snapshot.py` — Workspace context capture for MemPalace auto-save
- `todo.py` — TODO/FIXME/HACK marker scanner
- `tags.py` — ctags-style symbol indexer
- Type hints Phase 2: Full signatures for all 8 core tools
- OpenCode .ts wrappers for health, snapshot, todo, tags

### Changed
- Version bump 0.4.0 → 0.5.0
- Full mypy compliance across all tools
- 13 smoke tests (42+ checks) across all 14 tools
- README expanded with Health & Workspace section

## [0.4.0] — 2026-05-18

### Added
- `rename` — Word-boundary `\b` symbol rename
- `graph` — File-level dependency graph (imports, dependents, cycles)
- `changelog` — Formatted git log with conventional-commit grouping
- `search` — Rich grep with regex, file filters, context lines
- `lint` — Structured lint output parsing (ruff/eslint/tsc/mypy/pylint)
- `refactor` — AST-based rename (Python, no false positives)
- Type hints Phase 1
- Cross-platform CI with 3 OS × 3 Python versions

### Changed
- README fully rewritten with performance benchmarks
- Installer scripts unified (sh/ps1/bat)
- Performance: OOM guard (skip files >50MB), cross-drive safe on Windows

## [0.3.0] — 2026-05-10

### Added
- `hashline` — Hash-anchored content editing
- `impact` — Symbol impact analysis (Python, C++, TypeScript)
- `verify` — Post-edit verification
- `calltrace` — Recursive call chain analysis
- OpenCode plugin system (.ts wrappers)
- Installer scripts (install.sh, install.ps1, install.bat)

### Changed
- Initial public release
- MIT License
