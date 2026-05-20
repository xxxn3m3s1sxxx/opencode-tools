# OpenCode Tools — Reliability Toolbox for AI-Assisted Development

[![Tests](https://img.shields.io/badge/tools-2-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![Windows](https://img.shields.io/badge/windows-passing-brightgreen)]()
[![Linux](https://img.shields.io/badge/linux-passing-brightgreen)]()

A collection of OpenCode plugins that solve real problems in AI-assisted coding.
No external dependencies. Just Python 3 + zero-fuss install.

## Tools

### Verify — Post-Edit Verification

After every edit, know for sure it worked. Verify reads the file back and
confirms the expected change is present — or tells you exactly what's wrong.

```
verify atlas_api.cpp:20 "atlas_valloc"     Line 20 has atlas_valloc?
verify impact.py --old "bug" --new "fix"     Replace verified?
verify atlas_api.cpp                          File summary (lines, hash)
verify atlas_infer.py:612 --context 5         Context at line 612
```

**Status:** Beta — 48 tests · post-edit confidence check

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

### Trace — Recursive Call Chain Analysis

Follow execution paths through your codebase. Find who calls a function,
what it calls, and build full call trees.

```
trace forward                 Trace forward() through the codebase
trace generate_c --down -d 3  Deep dive into generate_c callees
trace AtlasModel --up         Who references AtlasModel?
trace load_model --viz        ASCII tree visualization
```

**Status:** Alpha — 28 tests · Python AST only, C++ via grep heuristics

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
|---|---|---|---|---|
| `edit()` | hashline.ts | hashline.py | Auto-fallback when string replace fails |
| `hashline_edit()` | hashline.ts | hashline.py | Explicit hash-anchored edit |
| `hashline_patch()` | hashline.ts | hashline.py | Raw hashline diff format |
| `hashline_stats()` | hashline.ts | hashline.py | Show intervention rate |
| `impact` | impact.ts | impact.py | Change impact analysis |
| `verify` | verify.ts | verify.py | Post-edit verification |
| `trace` | trace.ts | trace.py | Recursive call chain analysis |

## Project Structure

```
opencode-tools/
├── hashline.py             # Hashline engine (v0.3.0)
├── hashline.ts             # Hashline OpenCode plugin
├── test_hashline.py        # 42 core tests
├── regression_tests.py     # 22 regression tests
├── stress_test.py          # 39 stress tests
├── deeper_tests.py         # 27 deep edge tests
├── impact.py               # Impact engine (v0.1.1)
├── impact.ts               # Impact OpenCode plugin
├── test_impact.py          # 61 tests
├── verify.py               # Verify engine (v0.1.0)
├── verify.ts               # Verify OpenCode plugin
├── test_verify.py          # 48 tests
├── trace.py                # Trace engine (v0.1.0)
├── trace.ts                # Trace OpenCode plugin
├── test_trace.py           # 28 tests
├── install.sh              # Linux/macOS installer
├── install.ps1             # Windows installer
├── .github/workflows/ci.yml
├── package.json
└── README.md
```

## Test Status

```
hashline: 130/130  (42 core + 22 regression + 39 stress + 27 deep)
impact:   63/63    (Python AST + C++ regex + CLI + edge cases)
verify:   48/48    (read, contains, context, replace, CLI, edge cases)
trace:    28/28    (call chain, callers/callees, CLI, viz)
```

## Why Separate Tools?

Each tool solves one problem and solves it well. Combined install for
convenience, independent versioning for flexibility.

## License

MIT
