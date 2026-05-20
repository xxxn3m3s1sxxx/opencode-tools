# OpenCode Tools — Reliability Toolbox for AI-Assisted Development

[![Tools](https://img.shields.io/badge/tools-13-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![Tests](https://img.shields.io/badge/tests-366-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Windows](https://img.shields.io/badge/windows-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions)
[![Linux](https://img.shields.io/badge/linux-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions)
[![macOS](https://img.shields.io/badge/macos-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions)

A collection of OpenCode plugins that solve real problems in AI-assisted coding.
No external Python dependencies. Zero-fuss install.

## Tools

### Core Editing
| Tool | File | Description |
|------|------|-------------|
| `edit` | hashline.py | Edit file by finding and replacing text. Tries exact match, auto-retries with hash-anchored fallback. |
| `hashline_edit` | hashline.py | Explicit hash-anchored content edit. Handles trailing whitespace, indent mismatches, extra blank lines. |
| `hashline_patch` | hashline.py | Apply raw hashline diff format to a file. `@@ path / + ANCHOR~payload / - A..B` |
| `hashline_stats` | hashline.py | Show edit() intervention rate — how often direct match fails and hashline salvages. |

### Analysis
| Tool | File | Description |
|------|------|-------------|
| `impact` | impact.py | Change impact analyzer. Find definitions, references, tests, callers for any symbol. Python AST + C++ heuristics. |
| `verify` | verify.py | Post-edit verification. Confirm file has expected content, check line, context, old/new. |
| `trace` | trace.py | Recursive call chain analyzer. Follow execution paths: who calls a function, what it calls. |
| `graph` | graph.py | File-level dependency analyzer. Show imports, dependents, dependency trees, cycles. Python/TS/C++. |
| `search` | search.py | Rich grep wrapper with regex, file filters (--include), context lines (--context), JSON output. |
| `lint` | lint.py | Run project lint/typecheck and parse output into structured results. Supports ruff/eslint/tsc/mypy/pylint. |

### Refactoring
| Tool | File | Description |
|------|------|-------------|
| `rename` | rename.py | Word-boundary `\b` symbol renaming across all source files. Multi-language. |
| `refactor` | refactor.py | **AST-based** symbol renaming (Python). Safer than word-boundary — no false positives on partial matches. |

### History
| Tool | File | Description |
|------|------|-------------|
| `changelog` | changelog.py | Formatted git log with conventional-commit category grouping (feat/fix/docs/refactor/…). Auto-detects git root. |

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
# 1. Copy all plugin files + engines to OpenCode plugins dir
cp *.ts *.py ~/.config/opencode/plugins/

# 2. (Optional) Copy engines to project root for CLI usage
cp *.py /path/to/project/

# 3. Restart OpenCode
```

## Development

```bash
# Run all tests
python test_hashline.py
python test_impact.py
python test_verify.py
python test_trace.py
python test_graph.py
python test_changelog.py
python test_search.py
python test_lint.py
python test_refactor.py

# Deep test suites
python deeper_tests.py
python regression_tests.py
python stress_test.py
```

## Test Status (366+ tests, all green)

| Suite | Tests | Status |
|-------|-------|--------|
| hashline | 42 core + 22 regression + 39 stress + 27 deep = 130 | ✅ All pass |
| impact | 63 | ✅ All pass |
| verify | 48 | ✅ All pass |
| trace | 28 | ✅ All pass |
| graph | 20 | ✅ All pass |
| changelog | 25 | ✅ All pass |
| search | 14 | ✅ All pass |
| lint | 17 | ✅ All pass |
| refactor | 21 | ✅ All pass |

## Project Structure

```
opencode-tools/
├── utils.ts              # Shared utilities (detectPython, splitArgs)
├── hashline.py/.ts       # Hash-anchored editing (v0.3.0)
├── impact.py/.ts         # Change impact analysis (v0.1.1)
├── verify.py/.ts         # Post-edit verification (v0.1.0)
├── trace.py/.ts          # Recursive call chain (v0.1.0)
├── rename.py/.ts         # Word-boundary rename (v0.1.0)
├── graph.py/.ts          # Dependency graph (v0.1.0)
├── changelog.py/.ts      # Formatted git log (v0.1.0)
├── search.py/.ts         # Rich grep (v0.1.0)
├── lint.py/.ts           # Lint runner (v0.1.0)
├── refactor.py/.ts       # AST-based rename (v0.1.0)
├── test_*.py             # Test suites
├── deeper_tests.py       # 27 deep edge tests
├── regression_tests.py   # 22 regression tests
├── stress_test.py        # 39 stress tests
├── install.sh            # Linux/macOS installer
├── install.ps1           # Windows PowerShell installer
├── install.bat           # Windows cmd installer
├── .github/workflows/ci.yml
├── package.json
└── README.md
```

## Why Separate Tools?

Each tool solves one problem and solves it well. Combined install for
convenience, independent versioning for flexibility.

## Tech Stack
- **Plugins**: TypeScript, @opencode-ai/plugin v1.14.20
- **Engines**: Python 3.10+ (stdlib only — no external deps)
- **Tests**: Python unittest (no pytest required)

## License

MIT
