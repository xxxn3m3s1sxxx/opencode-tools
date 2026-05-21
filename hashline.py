#!/usr/bin/env python3
"""
hashline.py -- hash-anchored text editing — precision diffs for AI coding tools

Hashline: every line gets a 2-char content hash (xxHash32-style via SHA-256).
Edits reference LINE+HASH anchors instead of reproducing old text.

Usage:
  python hashline.py read <file>              # show file with hashes
  python hashline.py edit <file> <diff.txt>   # apply hashline edits
  python hashline.py check <file>             # show hashes only

Edit format (stdin or file):
  @@ path/to/file
  + 42sr           insert after anchor "42sr"
  ~new line        payload (starts with ~)
  < 42sr           insert before anchor
  ~another line
  = 10ab..15xy     replace range
  ~replacement
  - 20fg..20fg     delete line
  - 30hi..35zz     delete range
"""

VERSION = "0.3.0"

import hashlib
import itertools
import re
import sys

import string
from pathlib import Path

# Ensure stdout can handle unicode (fixes Windows cp1252 issues)
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass


def _read_file(path: Path) -> str:
    """Read file with UTF-8, stripping BOM and normalizing CRLF to LF."""
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


BIGRAMS = [a + b for a, b in itertools.product(string.ascii_lowercase, repeat=2)]
BIGRAMS_COUNT = len(BIGRAMS)

HL_BODY_SEP = "|"
HL_EDIT_SEP = "~"

RANGE_INTERIOR_HASH = "**"
BEGIN_PATCH = "*** Begin Patch"
END_PATCH = "*** End Patch"
ABORT_MARKER = "*** Abort"
FILE_HEADER = "@"


def compute_line_hash(line: str) -> str:
    """2-char content hash via SHA-256 mod 676."""
    cleaned = line.replace("\r", "").rstrip("\n")
    h = hashlib.sha256(cleaned.encode("utf-8")).digest()
    idx = int.from_bytes(h[:8], "little") % BIGRAMS_COUNT
    return BIGRAMS[idx]


def format_hash_line(line_number: int, line: str) -> str:
    """LINE+ID|TEXT"""
    return f"{line_number}{compute_line_hash(line)}{HL_BODY_SEP}{line}"


def format_hash_lines(text: str, start: int = 1) -> str:
    """Format entire file with hashline prefixes."""
    lines = text.split("\n")
    return "\n".join(format_hash_line(start + i, line) for i, line in enumerate(lines))


class HashlineError(Exception):
    """Base error for hashline operations."""

    def __init__(self, message: str, display_message: str = ""):
        super().__init__(message)
        self.display_message = display_message or message


class HashlineMismatchError(HashlineError):
    """Anchor hash does not match current file content."""

    def __init__(self, mismatches: list, file_lines: list[str]):
        self.mismatches = mismatches
        self.file_lines = file_lines
        msg = self._format_msg(mismatches, file_lines)
        display = self._format_display(mismatches, file_lines)
        super().__init__(msg, display)

    @staticmethod
    def _format_msg(mismatches, file_lines):
        noun = "anchors do" if len(mismatches) > 1 else "anchor does"
        lines = [f"Edit rejected: {len(mismatches)} {noun} not match the current file (marked *).",
                 "The edit was NOT applied. Use the updated content below:", ""]
        mismatch_set = {m[0] for m in mismatches}
        context_lines = set()
        for ln, _, _ in mismatches:
            for off in range(-2, 3):
                idx = ln + off
                if 1 <= idx <= len(file_lines):
                    context_lines.add(idx)
        prev = -1
        for ln in sorted(context_lines):
            if prev != -1 and ln > prev + 1:
                lines.append("...")
            prev = ln
            text = file_lines[ln - 1] if ln - 1 < len(file_lines) else ""
            h = compute_line_hash(text)
            marker = "*" if ln in mismatch_set else " "
            lines.append(f"{marker}{ln}{h}{HL_BODY_SEP}{text}")
        return "\n".join(lines)

    @staticmethod
    def _format_display(mismatches, file_lines):
        mismatch_set = {m[0] for m in mismatches}
        w = max(len(str(ln)) for ln in mismatch_set) if mismatch_set else 2
        lines = []
        prev = -1
        for ln in sorted(mismatch_set):
            if prev != -1 and ln > prev + 1:
                lines.append("...")
            prev = ln
            text = file_lines[ln - 1] if ln - 1 < len(file_lines) else ""
            lines.append(f"* {str(ln).rjust(w)}|{text}")
        return "\n".join(lines)


class HashlineParseError(HashlineError):
    """Invalid hashline edit syntax."""


def parse_anchor(raw: str) -> tuple[int, str]:
    """Parse '42sr' -> (42, 'sr')"""
    if raw != raw.lower():
        print(f"Warning: anchor {raw!r} has uppercase chars — lowercased automatically", file=sys.stderr)
    m = re.match(r"^(\d+)([a-z]{2})$", raw.lower())
    if not m:
        raise HashlineParseError(
            f"Invalid anchor {raw!r}. Expected format: LINE+HASH (e.g. 42sr)")
    return int(m.group(1)), m.group(2)


def parse_range(raw: str) -> tuple[tuple[int, str], tuple[int, str]]:
    """Parse '10ab..15xy' -> ((10,'ab'), (15,'xy'))"""
    parts = raw.split("..")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise HashlineParseError(f"Invalid range {raw!r}. Expected: LINE+HASH..LINE+HASH")
    start = parse_anchor(parts[0])
    end = parse_anchor(parts[1])
    if end[0] < start[0]:
        raise HashlineParseError(f"Range {raw} ends before it starts.")
    if end[0] == start[0] and end[1] != start[1]:
        raise HashlineParseError(f"Range {raw} has different hashes for same line.")
    return start, end


def expand_range(start: tuple[int, str], end: tuple[int, str]) -> list[tuple[int, str]]:
    """Expand a range to individual anchors. Interior lines get ** hash."""
    result = []
    for line in range(start[0], end[0] + 1):
        if line == start[0]:
            result.append((line, start[1]))
        elif line == end[0]:
            result.append((line, end[1]))
        else:
            result.append((line, RANGE_INTERIOR_HASH))
    return result


def parse_hashline(diff: str) -> list[dict]:
    """Parse hashline edit text into structured edit operations."""
    edits = []
    lines = diff.split("\n")
    edit_index = 0
    i = 0

    while i < len(lines):
        raw = lines[i].strip()
        line_num = i + 1

        if not raw or raw == BEGIN_PATCH or raw == END_PATCH or raw == ABORT_MARKER:
            i += 1
            continue

        # Insert after: + ANCHOR
        if m := re.match(r"^\+ (\S+)$", raw):
            cursor = _parse_insert_target(m.group(1), line_num, after=True)
            payload, i = _collect_payload(lines, i + 1, line_num, require=True)
            for text in payload:
                edits.append({"kind": "insert", "cursor": cursor, "text": text,
                              "line_num": line_num, "idx": edit_index})
                edit_index += 1
            continue

        # Insert before: < ANCHOR
        if m := re.match(r"^< (\S+)$", raw):
            cursor = _parse_insert_target(m.group(1), line_num, after=False)
            payload, i = _collect_payload(lines, i + 1, line_num, require=True)
            for text in payload:
                edits.append({"kind": "insert", "cursor": cursor, "text": text,
                              "line_num": line_num, "idx": edit_index})
                edit_index += 1
            continue

        # Delete: - A..B
        if m := re.match(r"^- (.+)$", raw):
            start_a, end_a = parse_range(m.group(1))
            for anchor in expand_range(start_a, end_a):
                edits.append({"kind": "delete", "anchor": anchor,
                              "line_num": line_num, "idx": edit_index})
                edit_index += 1
            i += 1
            continue

        # Replace: = A..B
        if m := re.match(r"^= (.+)$", raw):
            start_a, end_a = parse_range(m.group(1))
            payload, i = _collect_payload(lines, i + 1, line_num, require=False)
            content = payload if payload else [""]
            for text in content:
                edits.append({"kind": "insert",
                              "cursor": {"kind": "before_anchor", "anchor": start_a},
                              "text": text, "line_num": line_num, "idx": edit_index})
                edit_index += 1
            for anchor in expand_range(start_a, end_a):
                edits.append({"kind": "delete", "anchor": anchor,
                              "line_num": line_num, "idx": edit_index})
                edit_index += 1
            continue

        raise HashlineParseError(
            f"line {line_num}: unexpected {raw!r}. Use +, <, =, - or ~payload")

    return edits


def _parse_insert_target(raw: str, line_num: int, after: bool = False) -> dict:
    """Parse insert target: BOF, EOF, or LINE+HASH"""
    if raw.upper() == "BOF":
        return {"kind": "bof"}
    if raw.upper() == "EOF":
        return {"kind": "eof"}
    anchor = parse_anchor(raw)
    kind = "after_anchor" if after else "before_anchor"
    return {"kind": kind, "anchor": anchor}


def _collect_payload(lines: list[str], start: int, op_line: int, require: bool
                    ) -> tuple[list[str], int]:
    """Collect ~prefixed payload lines starting at index `start`."""
    payload = []
    i = start
    while i < len(lines):
        raw = lines[i].rstrip("\n")
        if raw.startswith(HL_EDIT_SEP):
            payload.append(raw[len(HL_EDIT_SEP):])
            i += 1
            continue
        break
    if require and not payload:
        raise HashlineParseError(
            f"line {op_line}: + and < ops need at least one ~payload line")
    return payload, i


def validate_anchors(edits: list[dict], file_lines: list[str]) -> list:
    """Check all anchor hashes against current file. Returns mismatches."""
    mismatches = []
    for edit in edits:
        anchors = _get_edit_anchors(edit)
        for line, expected_hash in anchors:
            if expected_hash == RANGE_INTERIOR_HASH:
                continue
            if line < 1 or line > len(file_lines):
                raise HashlineError(f"Line {line} does not exist (file has {len(file_lines)} lines)")
            actual = compute_line_hash(file_lines[line - 1])
            if actual != expected_hash:
                mismatches.append((line, expected_hash, actual))
    return mismatches


def _get_edit_anchors(edit: dict) -> list[tuple[int, str]]:
    """Extract all anchors from an edit."""
    if edit["kind"] == "delete":
        return [edit["anchor"]]
    cursor = edit.get("cursor", {})
    if cursor.get("kind") == "before_anchor" and "anchor" in cursor:
        return [cursor["anchor"]]
    return []


def _get_anchor_target_line(edit: dict) -> int | None:
    """Get the line number this edit targets."""
    if edit["kind"] == "delete":
        return edit["anchor"][0]
    cursor = edit.get("cursor", {})
    if cursor.get("kind") == "before_anchor":
        return cursor["anchor"][0]
    if cursor.get("kind") == "after_anchor":
        return cursor["anchor"][0]
    return None


def apply_hashline(text: str, edits: list[dict]) -> str:
    """Apply hashline edits to text. Returns modified text."""
    if not edits:
        return text

    file_lines = text.split("\n")
    mismatches = validate_anchors(edits, file_lines)
    if mismatches:
        raise HashlineMismatchError(mismatches, file_lines)

    # Normalize after_anchor -> before_anchor of next line
    for edit in edits:
        if edit["kind"] != "insert":
            continue
        cursor = edit.get("cursor", {})
        if cursor.get("kind") != "after_anchor":
            continue
        anchor_line = cursor["anchor"][0]
        if anchor_line >= len(file_lines):
            edit["cursor"] = {"kind": "eof"}
        else:
            next_content = file_lines[anchor_line]
            next_hash = compute_line_hash(next_content)
            edit["cursor"] = {"kind": "before_anchor",
                              "anchor": (anchor_line + 1, next_hash)}

    # Separate BOF, EOF, and anchored edits
    bof_lines = []
    eof_lines = []
    anchored = []

    for e in edits:
        if e["kind"] == "insert":
            c = e["cursor"]
            if c["kind"] == "bof":
                bof_lines.append(e["text"])
                continue
            if c["kind"] == "eof":
                eof_lines.append(e["text"])
                continue
        anchored.append(e)

    # Group anchored edits by target line, apply bottom-up
    by_line: dict[int, list[dict]] = {}
    for e in anchored:
        target = _get_anchor_target_line(e)
        if target is not None:
            by_line.setdefault(target, []).append(e)

    first_changed = None

    for line in sorted(by_line.keys(), reverse=True):
        bucket = by_line[line]
        bucket.sort(key=lambda x: x.get("idx", 0))
        idx = line - 1
        current = file_lines[idx] if idx < len(file_lines) else ""

        before = []
        delete_line = False

        for e in bucket:
            if e["kind"] == "insert":
                before.append(e["text"])
            elif e["kind"] == "delete":
                delete_line = True

        if not before and not delete_line:
            continue

        replacement = before if delete_line else before + [current]
        file_lines[idx:idx + 1] = replacement
        if first_changed is None or line < first_changed:
            first_changed = line

    # Apply BOF inserts
    if bof_lines:
        if len(file_lines) == 1 and file_lines[0] == "":
            file_lines = bof_lines
        else:
            file_lines = bof_lines + file_lines
        if first_changed is None:
            first_changed = 1

    # Apply EOF inserts
    if eof_lines:
        if len(file_lines) == 1 and file_lines[0] == "":
            file_lines = eof_lines
        else:
            file_lines = file_lines + eof_lines
        if first_changed is None:
            first_changed = len(file_lines) - len(eof_lines) + 1

    return "\n".join(file_lines)


def parse_hashline_input(text: str, default_path: str | None = None) -> list[tuple[str, str]]:
    """Split multi-section input into [(path, diff), ...].

    Format:
        @@ path/to/file
        ...edits...
        @@ another/file
        ...edits...
    """
    sections = []
    lines = text.split("\n")
    current_path = None
    current_lines = []

    def flush():
        if current_path is not None and current_lines:
            sections.append((current_path, "\n".join(current_lines)))

    for line in lines:
        stripped = line.strip()
        if stripped == END_PATCH or stripped == ABORT_MARKER:
            break
        if stripped == BEGIN_PATCH:
            continue
        m = re.match(r"^@+\s+(.+)$", stripped)
        if m:
            flush()
            current_path = m.group(1)
            current_lines = []
        else:
            current_lines.append(line)

    flush()

    if not sections and default_path:
        sections.append((default_path, text))

    return sections


def cmd_read(args: list[str]):
    """Read file with hashline formatting."""
    if not args:
        print("Usage: hashline.py read <file>", file=sys.stderr)
        sys.exit(1)
    path = Path(args[0])
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = _read_file(path)
    print(format_hash_lines(text))


def cmd_check(args: list[str]):
    """Show line hashes only (LINE+ID per line)."""
    if not args:
        print("Usage: hashline.py check <file>", file=sys.stderr)
        sys.exit(1)
    path = Path(args[0])
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    lines = _read_file(path).splitlines()
    for i, line in enumerate(lines, 1):
        h = compute_line_hash(line)
        print(f"{i}{h}")


def cmd_edit(args: list[str]):
    """Apply hashline edits to a file.

    Usage:
        hashline.py edit <file> <diff_file>
        hashline.py edit <file>            # reads diff from stdin
    """
    if not args:
        print("Usage: hashline.py edit <file> [diff_file]", file=sys.stderr)
        sys.exit(1)

    file_path = Path(args[0])
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if len(args) > 1:
        diff_text = _read_file(Path(args[1]))
    else:
        diff_text = sys.stdin.read().replace("\r\n", "\n")

    original = _read_file(file_path)
    text = original

    sections = parse_hashline_input(diff_text, default_path=str(file_path))
    for section_path, section_diff in sections:
        edits = parse_hashline(section_diff)
        text = apply_hashline(text, edits)

    if text != original:
        file_path.write_text(text, encoding="utf-8")
        print(f"Updated {file_path}")
    else:
        print(f"No changes to {file_path}")


def cmd_diff(args: list[str]):
    """Show hashline-formatted diff between file and proposed edits.

    Usage:
        hashline.py diff <file> <diff_file>
        hashline.py diff <file> <diff_file> --json
    """
    use_json = "--json" in args
    clean_args = [a for a in args if a != "--json"]

    if len(clean_args) < 1:
        print("Usage: hashline.py diff <file> [diff_file]", file=sys.stderr)
        sys.exit(1)

    file_path = Path(clean_args[0])
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if len(clean_args) > 1:
        diff_text = _read_file(Path(clean_args[1]))
    else:
        diff_text = sys.stdin.read().replace("\r\n", "\n")

    original = _read_file(file_path)
    text = original

    sections = parse_hashline_input(diff_text, default_path=str(file_path))
    for section_path, section_diff in sections:
        edits = parse_hashline(section_diff)
        text = apply_hashline(text, edits)

    import difflib
    orig_lines = original.split("\n")
    new_lines = text.split("\n")
    diff_lines = list(difflib.unified_diff(
        orig_lines, new_lines,
        fromfile=str(file_path), tofile=str(file_path), lineterm=""))

    if use_json:
        import json as _json
        print(_json.dumps({
            "file": str(file_path),
            "changed": original != text,
            "diff": "\n".join(diff_lines),
        }, indent=2))
    else:
        for line in diff_lines:
            print(line)


def cmd_replace(args: list[str]):
    """Replace old text with new text using hashline anchors.

    Usage:
        hashline.py replace <file> <old_text> <new_text>
        hashline.py replace <file> <old> <new> --flags

    Finds the exact old text in the file, computes hashline anchors,
    and applies the replacement with anchor validation.

    --dry-run: show hashline diff without writing
    --stdin-old: read old text from stdin (for multi-line)
    --stdin-new: read new text from stdin
    """
    import argparse
    parser = argparse.ArgumentParser(description="Replace text using hashline anchors")
    parser.add_argument("file", help="Target file")
    parser.add_argument("old", nargs="?", default=None, help="Old text to replace")
    parser.add_argument("new", nargs="?", default=None, help="New text")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--stdin-old", action="store_true", help="Read old text from stdin")
    parser.add_argument("--stdin-new", action="store_true", help="Read new text from stdin")
    parser.add_argument("--file-old", type=str, default=None, help="Read old text from file")
    parser.add_argument("--file-new", type=str, default=None, help="Read new text from file")
    parsed_args, _ = parser.parse_known_args(args)

    file_path = Path(parsed_args.file)
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    old_text = parsed_args.old
    new_text = parsed_args.new

    if parsed_args.file_old:
        old_text = _read_file(Path(parsed_args.file_old))
    if parsed_args.file_new:
        new_text = _read_file(Path(parsed_args.file_new))

    if parsed_args.stdin_old and parsed_args.stdin_new:
        stdin_data = sys.stdin.read().replace("\r\n", "\n")
        split_marker = "\n===OLD/NEW===\n"
        if split_marker in stdin_data:
            old_text, new_text = stdin_data.split(split_marker, 1)
        else:
            print("Error: --stdin-old and --stdin-new together require stdin with delimiter", file=sys.stderr)
            print("Format: <old_text>\\n===OLD/NEW===\\n<new_text>", file=sys.stderr)
            sys.exit(1)
    elif parsed_args.stdin_old:
        old_text = sys.stdin.read().replace("\r\n", "\n")
    elif parsed_args.stdin_new:
        new_text = sys.stdin.read().replace("\r\n", "\n")

    if old_text is None or new_text is None:
        parser.print_help()
        sys.exit(1)

    content = _read_file(file_path)
    file_lines = content.split("\n")

    # Normalize CRLF -> LF in old_text (in case of Windows-style line
    # endings from command-line arguments), then strip trailing whitespace
    # so match_lines doesn't include a spurious empty element.
    old_stripped = old_text.replace("\r\n", "\n").rstrip("\n")
    idx = content.find(old_stripped)
    if idx < 0:
        print("Error: old text not found in file", file=sys.stderr)
        sys.exit(1)
    match_text = old_stripped

    match_lines = match_text.split("\n")
    start_line = content[:idx].count("\n") + 1
    end_line = start_line + len(match_lines) - 1

    # Preserve surrounding text when match is partial (not whole line).
    # The match starts at idx in content. Compute leading text on start_line
    # and trailing text on end_line that are NOT part of the match.
    start_line_idx_in_content = content[:idx].rfind("\n") + 1  # 0 if at file start
    leading = content[start_line_idx_in_content:idx]

    match_end_in_content = idx + len(match_text)
    next_nl = content.find("\n", match_end_in_content)
    end_line_end = next_nl if next_nl >= 0 else len(content)
    trailing = content[match_end_in_content:end_line_end]

    replacement = leading + new_text + trailing
    # For multi-line replacement, the leading/trailing context keeps
    # text outside the match boundary on the first/last lines intact.
    if start_line == end_line:
        anchor_hash = compute_line_hash(file_lines[start_line - 1])
        diff = f"= {start_line}{anchor_hash}..{start_line}{anchor_hash}\n"
    else:
        first_hash = compute_line_hash(file_lines[start_line - 1])
        last_hash = compute_line_hash(file_lines[end_line - 1])
        diff = f"= {start_line}{first_hash}..{end_line}{last_hash}\n"
    for line in replacement.split("\n"):
        diff += f"{HL_EDIT_SEP}{line}\n"

    if parsed_args.dry_run:
        print(hashline_diff_output(diff, str(file_path)))
        return

    # Apply the hashline edit
    try:
        edits = parse_hashline(diff)
        result = apply_hashline(content, edits)
    except HashlineError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    if result != content:
        file_path.write_text(result, encoding="utf-8")
        print(f"Updated {file_path} ({start_line}-{end_line})")
    else:
        print("No changes made", file=sys.stderr)
        sys.exit(1)


def hashline_diff_output(diff: str, file_path: str = "path") -> str:
    """Format a hashline diff for display with file header."""
    return f"@@ {file_path}\n{diff}"


def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("--version", "-V"):
        print(f"hashline.py {VERSION}")
        sys.exit(0)

    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h", "-?"):
        print(__doc__, file=sys.stderr)
        sys.exit(0 if sys.argv[1:] else 1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "read": cmd_read,
        "check": cmd_check,
        "edit": cmd_edit,
        "diff": cmd_diff,
        "replace": cmd_replace,
    }

    if command not in commands:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Available: {}{}".format(
            ", ".join(commands),
            ", --version"
        ), file=sys.stderr)
        sys.exit(1)

    try:
        commands[command](args)
    except HashlineError as e:
        print(e.display_message if hasattr(e, 'display_message') and e.display_message else str(e),
              file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
