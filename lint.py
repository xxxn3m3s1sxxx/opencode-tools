#!/usr/bin/env python3
"""lint — run project lint/typecheck and parse output.

Usage:
  lint                            Run auto-detected lint command
  lint <tool>                     Run specific tool (ruff, eslint, tsc, mypy, pylint)
  lint <tool> <file>              Run on specific file
  lint [dir]                      Run auto-detected lint in directory
  lint --root <dir>               Set project root directory
  lint --json                     Structured JSON output with line:col:severity:message

Auto-detects: npm run lint, npm run typecheck, ruff, eslint, tsc --noEmit, mypy, pylint
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

PARSERS: list[tuple[str, re.Pattern, dict]] = []


def _register(name: str, pattern: str, fields: dict):
    PARSERS.append((name, re.compile(pattern), fields))


_register('ruff', r'^(.+?):(\d+):(\d+):\s+(\w+)\s+(.+)$',
          {'file': 1, 'line': 2, 'col': 3, 'severity': 4, 'message': 5})
_register('eslint', r'^(.+?):(\d+):(\d+):\s+(warning|error)\s+(.+)$',
          {'file': 1, 'line': 2, 'col': 3, 'severity': 4, 'message': 5})
_register('tsc', r'^(.+)\((\d+),(\d+)\):\s+(error|warning)\s+(.+)$',
          {'file': 1, 'line': 2, 'col': 3, 'severity': 4, 'message': 5})
_register('mypy', r'^(.+?):(\d+):\s+(error|warning|note):\s+(.+)$',
          {'file': 1, 'line': 2, 'severity': 3, 'message': 4})
_register('pylint', r'^(.+?):(\d+):(\d+):\s+(\w\d+):\s+(.+)$',
          {'file': 1, 'line': 2, 'col': 3, 'severity': 4, 'message': 5})
_register('generic', r'^(.+?):(\d+):\s+(.+)$',
          {'file': 1, 'line': 2, 'message': 3})


def _detect_cmd(root: str = ".") -> str | None:
    """Auto-detect which lint command to run."""
    pkg_json = os.path.join(root, "package.json")
    if os.path.exists(pkg_json):
        with open(pkg_json, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                scripts = data.get("scripts", {})
                for name in ["lint", "typecheck", "tsc"]:
                    if name in scripts:
                        cmd = scripts[name]
                        if cmd.startswith("npx ") or cmd.startswith("npm "):
                            return cmd
                        return f"npx {cmd}" if not cmd.startswith("node ") else cmd
            except (json.JSONDecodeError, OSError):
                pass
    return None


def _run_command(cmd: list[str], root: str) -> tuple[str, str, int]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding='utf-8', errors='replace',
                           timeout=60, cwd=root)
        return r.stdout, r.stderr, r.returncode
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", -1
    except subprocess.TimeoutExpired:
        return "", "Command timed out after 60s", -1
    except PermissionError:
        return "", f"Cannot execute: {cmd[0]}", -1


def _parse_output(output: str) -> list[dict]:
    results = []
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        for name, pattern, fields in PARSERS:
            m = pattern.match(line)
            if m:
                entry = {'_parser': name}
                for fname, group_num in fields.items():
                    val = m.group(group_num)
                    if fname in ('line', 'col'):
                        try:
                            val = int(val)
                        except (ValueError, TypeError):
                            pass
                    entry[fname] = val
                results.append(entry)
                break
    return results


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('--help', '-h'):
        print(__doc__.strip())
        return 0 if args and args[0] in ('--help', '-h') else 1

    if args[0] == '--version':
        print(f"lint.py {VERSION}")
        return 0

    root = os.getcwd()
    use_json = False
    tool = None
    file_arg = None

    raw = list(args)
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == '--json':
            use_json = True; i += 1
        elif a == '--root' and i + 1 < len(raw):
            root = raw[i + 1]; i += 2
        elif a.startswith('--root='):
            root = a.split('=', 1)[1]; i += 1
        elif a.startswith('-'):
            print(f"Unknown flag: {a}", file=sys.stderr); return 1
        elif tool is None:
            tool = a; i += 1
        else:
            file_arg = a; i += 1

    # If the positional arg is a directory, treat it as root
    if tool and os.path.isdir(tool) and file_arg is None:
        root = tool
        tool = None

    # Build command
    cmd: list[str] = []
    if tool == 'ruff' or (tool is None and _detect_cmd(root) is None):
        cmd = ['ruff', 'check', '.']
    elif tool == 'eslint':
        cmd = ['npx', 'eslint', '.']
    elif tool == 'tsc':
        cmd = ['npx', 'tsc', '--noEmit']
    elif tool == 'mypy':
        cmd = ['mypy']
    elif tool == 'pylint':
        cmd = ['pylint']
    elif tool is None:
        detected = _detect_cmd(root)
        if detected:
            cmd = detected.split()
        else:
            # Default: try ruff, fallback to eslint, tsc
            for candidate in [['ruff', 'check'], ['npx', 'eslint', '.'], ['npx', 'tsc', '--noEmit']]:
                try:
                    r = subprocess.run(candidate + ['--version' if candidate[0] != 'ruff' else '--version'],
                                       capture_output=True, timeout=5, cwd=root)
                    if r.returncode == 0:
                        cmd = candidate
                        break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            if not cmd:
                print("No lint tool detected. Try: lint ruff, lint eslint, lint tsc", file=sys.stderr)
                return 1
    else:
        # Unknown tool name - try running it directly
        cmd = [tool]

    if file_arg:
        cmd.append(file_arg)

    stdout, stderr, returncode = _run_command(cmd, root)
    full_output = stdout + stderr
    entries = _parse_output(full_output)

    if use_json:
        result = {
            'command': ' '.join(cmd),
            'exit_code': returncode,
            'tool': tool or 'auto',
            'issues': entries,
            'count': len(entries),
        }
        print(json.dumps(result, indent=2))
    else:
        if not entries:
            if returncode == 0:
                print("No issues found ✨")
            else:
                print(f"Command `{' '.join(cmd)}` exited with code {returncode}")
                print("Output could not be parsed. Raw output:")
                print(full_output[:2000])
        else:
            errors = [e for e in entries if e.get('severity') in ('error', 'E') or e.get('severity') == 'error']
            warnings = [e for e in entries if e.get('severity') in ('warning', 'W') or e.get('severity') == 'warning']
            info = [e for e in entries if e not in errors and e not in warnings]

            print(f"{len(errors)} error(s), {len(warnings)} warning(s), {len(info)} info(s)")
            print()

            for e in (errors + warnings + info)[:30]:
                sev = e.get('severity', '?').upper()[:1]
                loc = f"{e.get('file', '?')}:{e.get('line', '?')}"
                if 'col' in e:
                    loc += f":{e['col']}"
                msg = e.get('message', e.get('raw', '?'))
                print(f"  [{sev}] {loc}  {msg}")

            if len(entries) > 30:
                print(f"\n  ... and {len(entries) - 30} more issues")

    return 0 if returncode == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
