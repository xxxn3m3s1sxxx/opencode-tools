#!/usr/bin/env python3
"""changelog — formatted git log with category grouping.

Usage:
  changelog                       Recent commits (default: last 20)
  changelog -n 50                 Last 50 commits
  changelog v1.0..HEAD            Commits between tags
  changelog --from <ref>          Commits from a ref to HEAD
  changelog --to <ref>            Commits up to a ref
  changelog --range <a>..<b>      Commits between refs
  changelog --file <path>         Commits touching a specific file
  changelog --since <date>        Commits since date (e.g. '2024-01-01')
  changelog --root <dir>          Run in specific git repo directory
  changelog [dir]                 Alias for --root (positional)
  changelog --json                Raw JSON output (for plugin)

Categorizes commits by conventional-commit prefix
(feat/fix/docs/refactor/test/ci/chore/...).
"""
import json
import os
import re
import subprocess
import sys

VERSION = "0.1.0"

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

CATEGORIES = {
    'feat': 'Features',
    'feature': 'Features',
    'fix': 'Bug Fixes',
    'bugfix': 'Bug Fixes',
    'docs': 'Documentation',
    'doc': 'Documentation',
    'refactor': 'Refactoring',
    'refactoring': 'Refactoring',
    'test': 'Tests',
    'tests': 'Tests',
    'ci': 'CI',
    'chore': 'Chores',
    'perf': 'Performance',
    'perfomance': 'Performance',
    'style': 'Style',
    'build': 'Build',
    'revert': 'Reverts',
}

COMMIT_RE = re.compile(
    r'^(?P<hash>[a-f0-9]+) '
    r'(?:\((?P<scope>[^)]*)\)\s+)?'
    r'(?P<subject>.+)$',
)

CONVENTIONAL_RE = re.compile(
    r'^(?P<type>\w+)(?:\((?P<scope>[^)]*)\))?'
    r'(?P<breaking>!)?'
    r':\s*'
    r'(?P<subject>.+)$',
)


def _git_log(*args: str, cwd: str | None = None) -> str:
    cmd = ['git', 'log', '--oneline', '--date=short']
    cmd.extend(args)
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=15, cwd=cwd,
        )
        if r.returncode != 0:
            print(f"git error: {r.stderr.strip()}", file=sys.stderr)
            return ''
        return r.stdout
    except FileNotFoundError:
        print("git not found", file=sys.stderr)
        return ''
    except subprocess.TimeoutExpired:
        print("git log timed out", file=sys.stderr)
        return ''


def _parse_line(line: str) -> dict | None:
    m = COMMIT_RE.match(line)
    if not m:
        return None
    hash_val = m.group('hash')
    subject = m.group('subject')

    conv = CONVENTIONAL_RE.match(subject)
    if conv:
        typ = conv.group('type')
        cat = CATEGORIES.get(typ, typ.capitalize())
        scope = conv.group('scope') or ''
        breaking = bool(conv.group('breaking'))
        desc = conv.group('subject')
        return {
            'hash': hash_val,
            'category': cat,
            'scope': scope,
            'breaking': breaking,
            'subject': desc,
            'raw': subject,
        }

    # Fallback: treat as 'Other'
    return {
        'hash': hash_val,
        'category': 'Other',
        'scope': '',
        'breaking': False,
        'subject': subject,
        'raw': subject,
    }


def format_log(entries: list[dict]) -> str:
    cats: dict[str, list] = {}
    for e in entries:
        cat = e['category']
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(e)

    order = ['Features', 'Bug Fixes', 'Performance', 'Refactoring',
             'Tests', 'Documentation', 'Style', 'Build', 'CI', 'Chores',
             'Reverts', 'Other']

    lines = []
    for cat in order:
        if cat not in cats:
            continue
        lines.append(f'\n## {cat}')
        for e in cats[cat]:
            prefix = ':boom: ' if e['breaking'] else ''
            scope = f"**{e['scope']}:** " if e['scope'] else ''
            short_hash = e['hash'][:7]
            lines.append(f"- {scope}{prefix}{e['subject']} ({short_hash})")

    return '\n'.join(lines)


def main():
    args = sys.argv[1:]
    if not args:
        # Show recent commits by default (like `git log --oneline -20`)
        pass
    elif args[0] in ('--help', '-h'):
        print(__doc__.strip())
        return 0
    elif args[0] == '--version':
        print(f"changelog.py {VERSION}")
        return 0

    use_json = False
    count = 20
    git_args: list[str] = []
    cwd = os.getcwd()

    # Auto-detect git root
    try:
        _r = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True,
            encoding='utf-8', timeout=5,
        )
        if _r.returncode == 0:
            cwd = _r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    raw = list(args)
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == '--json':
            use_json = True
            i += 1
        elif a == '-n' and i + 1 < len(raw):
            try:
                count = int(raw[i + 1])
                i += 2
            except ValueError:
                print(f"Invalid count: {raw[i+1]}", file=sys.stderr)
                return 1
        elif a == '--from' and i + 1 < len(raw):
            git_args.extend([f'{raw[i+1]}..HEAD'])
            i += 2
        elif a == '--to' and i + 1 < len(raw):
            git_args.extend([f'HEAD..{raw[i+1]}'])
            i += 2
        elif a == '--range' and i + 1 < len(raw):
            git_args.append(raw[i + 1])
            i += 2
        elif a == '--file' and i + 1 < len(raw):
            git_args.extend(['--', raw[i + 1]])
            i += 2
        elif a == '--since' and i + 1 < len(raw):
            git_args.extend(['--since', raw[i + 1]]); i += 2
        elif a == '--root':
            cwd = raw[i + 1] if i + 1 < len(raw) else cwd
            i += 2
        elif a.startswith('--root='):
            cwd = a.split('=', 1)[1]; i += 1
        elif a.startswith('-'):
            count = int(a[1:]) if a[1:].isdigit() else count
            i += 1
        elif '..' in a:
            git_args.append(a); i += 1
        elif os.path.isdir(a):
            cwd = a; i += 1
        else:
            print(f"Unknown argument: {a}", file=sys.stderr); return 1

    # Build git log args
    if not git_args:
        git_args.append(f'-{count}')
    elif git_args and not any(a.startswith('-') for a in git_args if a.startswith('-')):
        git_args = [f'-{count}', *git_args]

    raw_output = _git_log(*git_args, cwd=cwd)
    if not raw_output:
        return 1

    entries = []
    for line in raw_output.strip().split('\n'):
        e = _parse_line(line)
        if e:
            entries.append(e)

    if use_json:
        print(json.dumps({'entries': entries, 'count': len(entries)}, indent=2))
    else:
        result = format_log(entries)
        print(result.strip())

    return 0


if __name__ == '__main__':
    sys.exit(main())
