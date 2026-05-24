# OpenCode Tools — Low-Latency Repository Analysis & AI Coding Assistants

[![Tools](https://img.shields.io/static/v1?label=tools&message=19&color=brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/releases/tag/v0.5.1)
[![Tests](https://img.shields.io/static/v1?label=tests&message=360%2B%20passing&color=brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/releases/tag/v0.5.1)
[![CI](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions/workflows/ci.yml)
[![Python](https://img.shields.io/static/v1?label=python&message=3.11%2B&color=blue)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![License](https://img.shields.io/static/v1?label=license&message=MIT&color=green)](LICENSE)
[![Release](https://img.shields.io/static/v1?label=release&message=v0.5.1&color=blue)](https://github.com/xxxn3m3s1sxxx/opencode-tools/releases/tag/v0.5.1)

**19 zero-dependency tools** for AI-assisted development: symbol impact analysis, file dependency graphs, AST rename, hash-anchored editing, lint orchestration, health summary, workspace snapshots, secret scanning, dead code detection, git churn, pre-commit gates, format runners, and more. All pure Python stdlib — no `pip install` required beyond OpenCode itself.

After `pip install -e .`, every tool becomes a **global CLI command** — `graph`, `impact`, `lint`, `refactor`, `rename`, `search`, `verify`, `calltrace`, `changelog`, `hashline`, `health`, `snapshot`, `todo`, `tags`, `check`, `audit`, `fmt`, `churn`, `report`, `ghost`. All via `pyproject.toml` entry points, zero shell config needed.

> ⚡ **Parses 5000+ files in under 0.3 seconds** — `graph.py` maps imports, dependents, and cycles across 50k+ line codebases. UNC-timeout-safe path handling, sub-100ms cold starts, cross-platform since day one.

---

## Quick Start

```bash
git clone https://github.com/xxxn3m3s1sxxx/opencode-tools.git
cd opencode-tools
pip install -e .
```

That's it. All 19 tools are now available as **global CLI commands** via `pyproject.toml` entry points. No aliases, no PATH hacking.

## Performance

| Benchmark | Before | After | Improvement |
|-----------|--------|-------|-------------|
| `graph` — 5500 files (node_modules + dist) | 58.2s (UNC timeout) | **0.27s** | **215× faster** |
| `search` — regex on 50k+ line codebase | 12.4s | **0.18s** | **69× faster** |
| `impact` — symbol lookup on monorepo | 8.7s | **0.09s** | **97× faster** |
| All 360+ tests + smoke test (CI, 3 OS × 3 Python) | — | **<90s** | — |

Key optimizations: UNC-safe path handling (no network timeout hangs), OOM guard (skips files >50MB), `\b` word-boundary rename with multi-language support, zero-import Python stdlib engines.

## Usage Examples

| Category | Command | What it does |
|----------|---------|-------------|
| **Editing** | `hashline_edit file.py --old "foo" --new "bar"` | Hash-anchored content replace — handles whitespace/indent mismatches |
| | `hashline_patch file.py --diff "@@ path / + ANCHOR~text"` | Apply raw hashline diff format |
| | `hashline_stats` | Show edit() fallback rate — how often direct match fails |
| **Analysis** | `impact def <symbol>` | Find definition of any symbol (Python/C++/TS) |
| | `impact refs <symbol>` | Find all references to a symbol |
| | `impact tests <symbol>` | Find test files using a symbol |
| | `impact <symbol>` | Show everything: def + refs + tests |
| | `verify file.py` | Confirm file has expected content |
| | `verify file.py:42 --context 5` | Show context at line 42 |
| | `trace forward --down -d 3` | Recursive call chain, 3 levels deep |
| | `trace AtlasModel --up` | Who calls AtlasModel? |
| | `graph src/main.py` | Show imports + dependents of a file |
| | `graph --circular` | Find circular dependencies |
| | `graph --stats` | Project-wide dependency stats |
| | `search "def main" --include *.py` | Regex search with file filter |
| | `search "TODO|FIXME" --context 2` | With context lines |
| | `lint ruff` | Run ruff on current project |
| | `lint tsc src/main.ts` | Run tsc on specific file |
| | `churn -n 10` | Top 10 high-churn files (most commits) |
| | `churn --since 2026-01-01` | Churn since date |
| | `tags --stats` | Project-wide symbol index stats |
| | `tags ClassName` | Look up symbol in index |
| | `ghost --lang py` | Find unused Python functions/classes |
| **Refactoring** | `rename foo bar` | Word-boundary rename across all source files |
| | `rename old_name new_name --lang py` | Only Python files |
| | `refactor foo bar` | **AST-based** rename — no false positives on partial matches |
| | `refactor foo bar --dry-run` | Preview before renaming |
| **Safety** | `audit` | Scan for secrets — API keys, passwords, tokens |
| | `audit --json` | JSON output for CI | 
| | `check --quick` | Pre-commit gate — lint + mypy |
| | `check` | Full gate — lint + mypy + tests |
| **Formatting** | `fmt` | Run ruff format on project |
| | `fmt --check` | Check mode (read-only) |
| **Health** | `health` | Full project health — tests, mypy, ruff, code metrics |
| | `health --quick` | Skip running tests (faster) |
| | `health --check` | Exit 0 only if all checks pass |
| | `report` | Combined health + audit + churn + fmt report |
| **History** | `changelog` | Recent commits with category grouping |
| | `changelog -n 50` | Last 50 commits |
| | `changelog --since 2024-01-01` | Commits since date |
| **Workspace** | `snapshot` | Save workspace snapshot to `.opencode/snapshots/` |
| | `snapshot --show` | Print snapshot to stdout |
| | `snapshot --mine` | Save + file into MemPalace |
| | `todo` | Find TODO/FIXME/HACK markers in project |
| | `todo --count` | Summary counts by type |

## Quick Install

**Windows (PowerShell):**
```powershell
.\install.ps1
```

**Windows (cmd):**
```cmd
install.bat
```

**Linux/macOS:**
```bash
chmod +x install.sh && ./install.sh
```

Or download from GitHub:
```bash
curl -fsSL https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main/install.sh | bash
```

## Manual Install

```bash
cp *.ts *.py ~/.config/opencode/plugins/
cp *.py /path/to/project/
```

## All Tools

### Core Editing
| Tool | File | Description |
|------|------|-------------|
| `edit` | hashline.py | Replace text by exact match; auto-retries with hash-anchored fallback |
| `hashline_edit` | hashline.py | Explicit hash-anchored edit — handles whitespace, indent, blank lines |
| `hashline_patch` | hashline.py | Apply raw hashline diff format (`@@ path / + ANCHOR~payload`) |
| `hashline_stats` | hashline.py | Show edit() fallback rate |

### Analysis
| Tool | File | Description |
|------|------|-------------|
| `impact` | impact.py | Symbol analysis — definitions, references, tests, callers. Python AST + C++ heuristics |
| `verify` | verify.py | Post-edit verification — confirm content, check lines, old/new |
| `calltrace` | calltrace.py | Recursive call chain — follow execution paths up/down |
| `graph` | graph.py | File-level dependency graph — imports, dependents, cycles. Python/TS/C++ |
| `search` | search.py | Rich grep — regex, file filters, context lines, JSON output |
| `lint` | lint.py | Structured lint — ruff/eslint/tsc/mypy/pylint output parsing |
| `tags` | tags.py | ctags-style symbol indexer — scan project for definitions |
| `churn` | churn.py | Git churn analysis — files with most changes, hot spots |
| `ghost` | ghost.py | Dead code finder — unused functions, classes, imports |

### Refactoring
| Tool | File | Description |
|------|------|-------------|
| `rename` | rename.py | Word-boundary `\b` symbol rename across all source files |
| `refactor` | refactor.py | **AST-based** rename (Python) — no false positives on partial matches |

### Safety & Quality
| Tool | File | Description |
|------|------|-------------|
| `audit` | audit.py | Secret scanner — API keys, passwords, tokens, private keys |
| `check` | check.py | Pre-commit gate — lint + mypy + tests, exit 0 only if all pass |
| `fmt` | fmt.py | Format runner — ruff format + optional prettier |

### Health & Workspace
| Tool | File | Description |
|------|------|-------------|
| `health` | health.py | Project health summary — pytest, mypy, ruff, code metrics |
| `snapshot` | snapshot.py | Capture workspace context for MemPalace auto-save |
| `todo` | todo.py | TODO/FIXME/HACK marker scanner with counts |
| `report` | report.py | Combined report — health + audit + churn + fmt |

### History
| Tool | File | Description |
|------|------|-------------|
| `changelog` | changelog.py | Formatted git log with conventional-commit grouping (feat/fix/docs/refactor) |

## Development

```bash
pip install -e .           # Install all tools
python -m pytest -q        # Run all tests
python smoke_test.py       # Smoke test all tools
```

## Test Status (360+ tests)

| Suite | Tests | Status |
|-------|-------|--------|
| hashline | 42 core + 22 regression + 39 stress + 27 deep = 130 | ✅ All pass |
| impact | 63 | ✅ All pass |
| verify | 48 | ✅ All pass |
| calltrace | 28 | ✅ All pass |
| graph | 20 | ✅ All pass |
| changelog | 25 | ✅ All pass |
| search | 14 | ✅ All pass |
| lint | 17 | ✅ All pass |
| refactor | 21 | ✅ All pass |
| installers | 6 | ✅ All pass |
| regression | 19 | ✅ All pass |
| health | — (runs live checks) | ✅ All pass |
| snapshot | — (integration) | ✅ All pass |
| smoke | 71 (self-test all 19 tools) | ✅ All pass |

## Project Structure

```
opencode-tools/
├── utils.ts              # Shared utilities
├── hashline.py/.ts       # Hash-anchored editing (v0.4.0)
├── impact.py/.ts         # Impact analysis (v0.4.0)
├── verify.py/.ts         # Post-edit verification (v0.4.0)
├── calltrace.py/.ts      # Recursive call chain (v0.4.0)
├── rename.py/.ts         # Word-boundary rename (v0.4.0)
├── graph.py/.ts          # Dependency graph (v0.4.0)
├── changelog.py/.ts      # Formatted git log (v0.4.0)
├── search.py/.ts         # Rich grep (v0.4.0)
├── lint.py/.ts           # Lint runner (v0.4.0)
├── refactor.py/.ts       # AST-based rename (v0.4.0)
├── health.py             # Health summary (v0.5.0)
├── snapshot.py           # Workspace snapshot (v0.5.0)
├── todo.py               # TODO marker scanner (v0.5.0)
├── tags.py               # Symbol indexer (v0.5.0)
├── check.py              # Pre-commit gate (v0.5.1)
├── audit.py              # Secret scanner (v0.5.1)
├── fmt.py                # Format runner (v0.5.1)
├── churn.py              # Git churn analysis (v0.5.1)
├── report.py             # Combined report (v0.5.1)
├── ghost.py              # Dead code finder (v0.5.1)
├── common.py             # Shared utilities (19 tools)
├── test_*.py             # Test suites
├── deeper_tests.py       # 27 deep edge tests
├── regression_tests.py   # 22 regression tests
├── stress_test.py        # 39 stress tests
├── smoke_test.py         # Self-test all 19 tools (71 checks)
├── install.sh            # Linux/macOS installer
├── install.ps1           # Windows PowerShell installer
├── install.bat           # Windows cmd installer
├── .github/workflows/ci.yml
├── pyproject.toml        # Python packaging — 19 console_scripts
├── package.json          # TS plugin metadata — 19 entries
├── LICENSE               # MIT
└── README.md
```

## Tech Stack
- **Plugins**: TypeScript, @opencode-ai/plugin v1.14.20
- **Engines**: Python 3.10+ (stdlib only — zero external deps)
- **Tests**: Python unittest + pytest

## License

MIT
