# OpenCode Tools — Reliability Toolbox for AI-Assisted Development

[![Tests](https://img.shields.io/badge/tools-2-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![Windows](https://img.shields.io/badge/windows-passing-brightgreen)]()
[![Linux](https://img.shields.io/badge/linux-passing-brightgreen)]()

A collection of OpenCode plugins that solve real problems in AI-assisted coding.
No external dependencies. Just Python 3 + zero-fuss install.

## Tools

### Hashline — Hash-Anchored Editing

`edit()` fails when the AI model reproduces old text with trailing whitespace,
wrong indentation, or extra blank lines. Hashline catches those failures
transparently with auto-fallback.

```
edit() → direct match OK           → applied immediately
edit() → "oldString not found"     → hashline retries → applied
edit() → hashline also fails       → clear error with hints
```

**Status:** Stable — 130/130 tests · 3 real bugs found and fixed

### Impact — Change Impact Analyzer

Before you edit a symbol, know what depends on it. Impact finds definitions,
references, tests, and callers across your codebase.

```
impact atlas_valloc        → 2 defs · 19 refs · 0 tests
impact AtlasModel --py      → class def + 50 references
impact atlas_infer.py:152   → infer symbol from file:line
impact graph generate_c     → 1 def · 1 ref · 20 callees
```

**Status:** Beta — Python AST + C++ heuristics · needs real-world testing

## Quick Install

```bash
# One command — auto-detects everything
curl -fsSL https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main/install.sh | sh

# Windows
.\install.ps1
```

## Manual Install

```bash
# 1. Copy plugins to OpenCode
cp hashline.ts ~/.config/opencode/plugins/
cp impact.ts ~/.config/opencode/plugins/

# 2. Copy engines to your project
cp hashline.py /path/to/project/
cp impact.py /path/to/project/

# 3. Restart OpenCode
```

## Tools Added

| Tool | Plugin | Engine | Purpose |
|---|---|---|---|
| `edit()` | hashline.ts | hashline.py | Auto-fallback when string replace fails |
| `hashline_edit()` | hashline.ts | hashline.py | Explicit hash-anchored edit |
| `hashline_patch()` | hashline.ts | hashline.py | Raw hashline diff format |
| `hashline_stats()` | hashline.ts | hashline.py | Show intervention rate |
| `impact` | impact.ts | impact.py | Change impact analysis |

## Project Structure

```
opencode-tools/
├── hashline.py             # Hashline engine (v0.3.0)
├── hashline.ts             # Hashline OpenCode plugin
├── test_hashline.py        # 42 core tests
├── regression_tests.py     # 22 regression tests
├── stress_test.py          # 39 stress tests
├── deeper_tests.py         # 27 deep edge tests
├── impact.py               # Impact engine (v0.1.0)
├── impact.ts               # Impact OpenCode plugin
├── install.sh              # Linux/macOS installer
├── install.ps1             # Windows installer
├── .github/workflows/ci.yml
├── package.json
└── README.md
```

## Test Status

```
hashline: 130/130 ✅  (42 core + 22 regression + 39 stress + 27 deep)
impact:   TBD
```

## Why Separate Tools?

Each tool solves one problem and solves it well. Combined install for
convenience, independent versioning for flexibility.

## License

MIT
