# OpenCode Tools — Low-Latency Repository Analysis & AI Coding Assistants

[![Tools](https://img.shields.io/badge/tools-13-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![Tests](https://img.shields.io/badge/tests-366-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![Speed](https://img.shields.io/badge/parse-5000+_files_in_&lt;0.3s-blue)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/xxxn3m3s1sxxx/opencode-tools)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Windows](https://img.shields.io/badge/windows-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions)
[![Linux](https://img.shields.io/badge/linux-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions)
[![macOS](https://img.shields.io/badge/macos-passing-brightgreen)](https://github.com/xxxn3m3s1sxxx/opencode-tools/actions)

**13 zero-dependency tools** for AI-assisted development: symbol impact analysis, file dependency graphs, AST rename, hash-anchored editing, lint orchestration, and more. All pure Python stdlib — no `pip install` required beyond OpenCode itself.

> ⚡ **Parses 5000+ files in under 0.3 seconds** — `graph.py` maps imports, dependents, and cycles across 50k+ line codebases with UNC-safe path handling and sub-100ms cold starts.

---

## Quick Start

```bash
git clone https://github.com/xxxn3m3s1sxxx/opencode-tools.git
cd opencode-tools
pip install -e .
```

That's it. All 13 tools are now available as CLI commands. No `npm install`, no `requirements.txt`, no virtualenv dance.

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
| **Refactoring** | `rename foo bar` | Word-boundary rename across all source files |
| | `rename old_name new_name --lang py` | Only Python files |
| | `refactor foo bar` | **AST-based** rename — no false positives on partial matches |
| | `refactor foo bar --dry-run` | Preview before renaming |
| **History** | `changelog` | Recent commits with category grouping |
| | `changelog -n 50` | Last 50 commits |
| | `changelog --since 2024-01-01` | Commits since date |

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
| `trace` | trace.py | Recursive call chain — follow execution paths up/down |
| `graph` | graph.py | File-level dependency graph — imports, dependents, cycles. Python/TS/C++ |
| `search` | search.py | Rich grep — regex, file filters, context lines, JSON output |
| `lint` | lint.py | Structured lint — ruff/eslint/tsc/mypy/pylint output parsing |

### Refactoring
| Tool | File | Description |
|------|------|-------------|
| `rename` | rename.py | Word-boundary `\b` symbol rename across all source files |
| `refactor` | refactor.py | **AST-based** rename (Python) — no false positives on partial matches |

### History
| Tool | File | Description |
|------|------|-------------|
| `changelog` | changelog.py | Formatted git log with conventional-commit grouping (feat/fix/docs/refactor) |

## Development

```bash
python test_hashline.py
python test_impact.py
python test_verify.py
python test_trace.py
python test_graph.py
python test_changelog.py
python test_search.py
python test_lint.py
python test_refactor.py
python deeper_tests.py
python regression_tests.py
python stress_test.py
```

## Test Status (366+ tests)

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
├── utils.ts              # Shared utilities
├── hashline.py/.ts       # Hash-anchored editing (v0.3.0)
├── impact.py/.ts         # Impact analysis (v0.1.1)
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
├── pyproject.toml        # Python packaging
├── package.json          # TS plugin metadata
├── LICENSE               # MIT
└── README.md
```

## Tech Stack
- **Plugins**: TypeScript, @opencode-ai/plugin v1.14.20
- **Engines**: Python 3.10+ (stdlib only — zero external deps)
- **Tests**: Python unittest (no pytest required)

## License

MIT
