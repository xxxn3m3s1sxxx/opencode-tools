#!/usr/bin/env python3
"""verify — post-edit verification tool. Confirm edits were applied correctly.

Commands:
  verify <file>                            Show file summary (size, lines, checksum)
  verify <file>:<line>                     Show context around a line
  verify <file> <text>                     Check if text exists in file
  verify <file>:<line> <text>              Check if text is at that line
  verify <file> --old <old> --new <new>    Confirm old removed + new present

Options:
  --context N              Show N lines of context (default: 3)
  --not <text>             Assert text is NOT present
  --contains <text>        Assert text IS present
  --line N                 Check specific line number
  --json                   JSON output (for plugin)

Exit code:
  0 = all checks passed
  1 = any check failed
"""

import hashlib
import json
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def _read_file(filepath):
    """Read file content, return (lines, raw)."""
    try:
        with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
        raw = raw.replace("\r\n", "\n")
        lines = raw.split("\n") if raw else []
        if lines and not lines[-1]:
            lines = lines[:-1]
        return lines, raw
    except FileNotFoundError:
        return None, None
    except (UnicodeDecodeError, OSError):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8", errors="replace")
            return text.splitlines(), text
        except OSError:
            return None, None


def _checksum(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _find_line(lines, text):
    """Find line number containing text (case-insensitive, 1-indexed)."""
    pattern = re.compile(re.escape(text), re.IGNORECASE)
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i + 1
    return None


def _count_matches(lines, text):
    pattern = re.compile(re.escape(text), re.IGNORECASE)
    return sum(1 for line in lines if pattern.search(line))


def cmd_summary(filepath, lines, raw):
    """Show file summary."""
    return {
        "status": "ok",
        "check": "summary",
        "file": filepath,
        "lines": len(lines),
        "bytes": len(raw),
        "checksum": _checksum(raw),
    }


def cmd_context(filepath, lines, raw, target_line, context=3):
    """Show context around a line."""
    total = len(lines)
    if target_line < 1 or target_line > total:
        return {"status": "error", "check": "context", "message": f"line {target_line} out of range (1-{total})"}

    start = max(0, target_line - context)
    end = min(total, target_line + context + 1)

    ctx = []
    for i in range(start, end):
        ctx.append(
            {
                "line": i + 1,
                "content": lines[i],
                "is_target": (i + 1) == target_line,
            }
        )

    return {
        "status": "ok",
        "check": "context",
        "file": filepath,
        "target_line": target_line,
        "total_lines": total,
        "context": ctx,
    }


def cmd_diff(filepath, staged=False, context_lines=3):
    """Show git diff for a file."""
    try:
        # Check if file is git-tracked
        ls = subprocess.run(["git", "ls-files", "--error-unmatch", filepath], capture_output=True, timeout=5)
        if ls.returncode != 0:
            return {"status": "ok", "check": "diff", "file": filepath, "diff": "(not a git repo or file not tracked)"}
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")
        cmd.extend(["--", filepath])
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        stdout = result.stdout.decode("utf-8", errors="replace")
        stderr = result.stderr.decode("utf-8", errors="replace")
        if result.returncode != 0:
            return {"status": "error", "message": f"git diff failed: {stderr.strip()}"}
        diff = stdout.strip()
        if not diff:
            return {"status": "ok", "check": "diff", "file": filepath, "diff": "(no changes)"}
        return {"status": "ok", "check": "diff", "file": filepath, "diff": diff}
    except FileNotFoundError:
        return {"status": "ok", "check": "diff", "file": filepath, "diff": "(git not found)"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "git diff timed out"}


def cmd_contains(filepath, lines, raw, text, should_exist=True):
    """Check if text exists (or doesn't exist) in file."""
    found_line = _find_line(lines, text)
    count = _count_matches(lines, text)

    if should_exist:
        ok = found_line is not None
        return {
            "status": "ok" if ok else "fail",
            "check": "contains",
            "text": text,
            "found": ok,
            "line": found_line,
            "count": count,
        }
    else:
        ok = found_line is None
        return {
            "status": "ok" if ok else "fail",
            "check": "not_contains",
            "text": text,
            "found": not ok,
            "line": found_line,
            "count": count,
        }


def cmd_line_check(filepath, lines, raw, line_no, expected_text):
    """Check content at a specific line."""
    total = len(lines)
    if line_no < 1 or line_no > total:
        return {"status": "error", "message": f"line {line_no} out of range (1-{total})"}

    actual = lines[line_no - 1]
    ok = expected_text in actual

    return {
        "status": "ok" if ok else "fail",
        "check": "line_content",
        "file": filepath,
        "line": line_no,
        "expected": expected_text,
        "actual": actual[:200],
        "match": ok,
    }


def cmd_replace_verify(filepath, lines, raw, old_text, new_text):
    """After a replace: confirm old is gone and new is present."""
    old_found = _find_line(lines, old_text)
    new_found = _find_line(lines, new_text)
    old_count = _count_matches(lines, old_text)
    new_count = _count_matches(lines, new_text)

    old_ok = old_found is None
    new_ok = new_found is not None

    all_ok = old_ok and new_ok

    return {
        "status": "ok" if all_ok else "fail",
        "check": "replace_verify",
        "file": filepath,
        "old_removed": old_ok,
        "old_line": old_found,
        "old_count": old_count,
        "old_text": old_text,
        "new_present": new_ok,
        "new_line": new_found,
        "new_count": new_count,
        "new_text": new_text,
    }


def format_pretty(result):
    """Human-readable output."""
    status = result.get("status", "error")

    if status == "ok":
        icon = "[OK]"
    elif status == "fail":
        icon = "[FAIL]"
    else:
        icon = "[ERROR]"

    lines = [f"  {icon} verify"]

    check = result.get("check", "summary")

    if check == "summary":
        lines.append(f"    file:   {result.get('file', '?')}")
        lines.append(f"    lines:  {result.get('lines', '?')}")
        lines.append(f"    bytes:  {result.get('bytes', '?')}")
        lines.append(f"    sha256: {result.get('checksum', '?')}")

    elif check == "contains":
        if result["found"]:
            lines.append(f'    "{result["text"]}" found at line {result["line"]} ({result["count"]}x)')
        else:
            lines.append(f'    "{result["text"]}" not found ❌')

    elif check == "not_contains":
        if not result["found"]:
            lines.append(f'    "{result["text"]}" confirmed absent ✅')
        else:
            lines.append(
                f'    "{result["text"]}" found at line {result["line"]} ({result["count"]}x) — expected absent ❌'
            )

    elif check == "line_content":
        if result["match"]:
            lines.append(f"    line {result['line']}: matches expected ✅")
            lines.append(f"      content: {result['actual']}")
        else:
            lines.append(f"    line {result['line']}: MISMATCH ❌")
            lines.append(f"      expected: {result['expected']}")
            lines.append(f"      actual:   {result['actual']}")

    elif check == "replace_verify":
        old_s = "[OK]" if result["old_removed"] else "[FAIL]"
        new_s = "[OK]" if result["new_present"] else "[FAIL]"
        old_t = result.get("old_text", "")
        lines.append(
            f'    old removed:    {old_s}  ("{old_t[:50]}" was at line {result["old_line"]}, {result["old_count"]}x)'
            if not result["old_removed"]
            else f"    old removed:    {old_s}"
        )
        lines.append(
            f"    new present:    {new_s}  (line {result['new_line']}, {result['new_count']}x)"
            if result["new_present"]
            else f"    new present:    {new_s}"
        )
        if result["status"] == "ok":
            lines.append("    edit verified ✅")
        else:
            lines.append("    edit NOT verified ❌")

    elif check == "diff":
        diff = result.get("diff", "")
        if diff == "(no changes)":
            lines.append(f"    no changes for {result.get('file', '?')}")
        else:
            for line in diff.split("\n"):
                lines.append(f"    {line}")

    elif check == "context":
        for ctx in result.get("context", []):
            marker = ">" if ctx["is_target"] else " "
            lines.append(f"    {marker} {ctx['line']:4d}: {ctx['content'][:120]}")

    elif "message" in result:
        lines.append(f"    {result['message']}")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        return 1
    if sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0

    args = sys.argv[1:]

    # Handle --version before flag parsing
    if args and args[0] == "--version":
        print("verify.py 0.1.0")
        return 0

    # Parse flags
    use_json = "--json" in args
    context_lines = 3
    not_mode = False
    contains_mode = False
    diff_mode = False
    diff_staged = False

    clean_args = []
    old_text = None
    new_text = None
    line_no = None

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            i += 1
            continue
        if a == "--diff":
            diff_mode = True
            i += 1
            continue
        if a == "--staged":
            diff_staged = True
            i += 1
            continue
        if a == "--context" and i + 1 < len(args):
            try:
                context_lines = int(args[i + 1])
            except ValueError:
                print(f"Invalid --context value: {args[i + 1]}", file=sys.stderr)
                return 1
            i += 2
            continue
        if a == "--not":
            not_mode = True
            i += 1
            continue
        if a == "--contains":
            contains_mode = True
            i += 1
            continue
        if a == "--line" and i + 1 < len(args):
            line_no = int(args[i + 1])
            i += 2
            continue
        if a == "--old" and i + 1 < len(args):
            old_text = args[i + 1]
            i += 2
            continue
        if a == "--new" and i + 1 < len(args):
            new_text = args[i + 1]
            i += 2
            continue
        if a.startswith("--"):
            print(f"Unknown flag: {a}")
            return 1
        clean_args.append(a)
        i += 1

    if not clean_args:
        print(__doc__.strip())
        return 1

    file_ref = clean_args[0]
    arg_text = " ".join(clean_args[1:]) if len(clean_args) > 1 else None

    # Parse file:line (--line flag already parsed)
    filepath = file_ref
    if ":" in file_ref:
        parts = file_ref.rsplit(":", 1)
        if parts[1].isdigit():
            filepath = parts[0]
            line_no = int(parts[1])

    # Diff mode doesn't need file read
    if diff_mode:
        result = cmd_diff(filepath, staged=diff_staged)
        if use_json:
            print(json.dumps(result, indent=2))
        else:
            print(format_pretty(result))
        return 0 if result.get("status") == "ok" else 1

    lines, raw = _read_file(filepath)
    if lines is None:
        print(f"  [ERROR] File not found: {filepath}")
        return 1

    # Determine command
    result = None

    if old_text is not None and new_text is not None:
        # replace verification
        result = cmd_replace_verify(filepath, lines, raw, old_text, new_text)

    elif line_no is not None and arg_text:
        # Check specific line content
        result = cmd_line_check(filepath, lines, raw, line_no, arg_text)

    elif not_mode:
        # Assert text NOT present
        text = arg_text or ""
        result = cmd_contains(filepath, lines, raw, text, should_exist=False)

    elif contains_mode:
        # Assert text IS present
        text = arg_text or ""
        result = cmd_contains(filepath, lines, raw, text, should_exist=True)

    elif line_no is not None and not arg_text:
        # Show context at line
        result = cmd_context(filepath, lines, raw, line_no, context_lines)

    elif arg_text:
        # Check if text exists
        result = cmd_contains(filepath, lines, raw, arg_text, should_exist=True)

    else:
        # File summary
        result = cmd_summary(filepath, lines, raw)

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(format_pretty(result))

    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
