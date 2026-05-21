#!/usr/bin/env python3
"""Targeted regression tests for recently fixed bugs."""
import os
import subprocess
import sys
import tempfile

HL = os.path.join(os.path.dirname(__file__), "..", "hashline.py")
if not os.path.exists(HL):
    HL = os.path.join(os.path.dirname(__file__), "hashline.py")
P = sys.executable

failed = 0
total = 0


def check(desc, cond, detail=""):
    global total, failed
    total += 1
    if cond:
        print(f"  [OK] {desc}")
    else:
        print(f"  [FAIL] {desc}  {detail}")
        failed += 1


def hl(*args, stdin=""):
    return subprocess.run(
        [P, HL] + list(args),
        input=stdin, capture_output=True, text=True,
        encoding="utf-8", timeout=30,
    )


# 1. CRLF in old_text (regression for fix #1)
with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
    f.write(b"hello\r\nworld\r\n")
    p = f.name
r = hl("replace", p, "hello\r\nworld", "REPLACED")
check("CRLF old_text matches", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("CRLF result correct", "REPLACED" in content, repr(content))
os.unlink(p)

# 2. Trailing newline in old_text (regression for fix #2)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("delete me\nkeep me\n")
    p = f.name
r = hl("replace", p, "delete me\n", "")
check("old_text with trailing nl matches", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("trailing nl result", content.strip() == "keep me", repr(content))
os.unlink(p)

# 3. Double trailing newlines in old_text
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("a\n\nb\n")
    p = f.name
r = hl("replace", p, "a\n\n", "A")
check("double trailing nl", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("double trailing nl result", "b" in content and "A" in content, repr(content))
os.unlink(p)

# 4. Multi-line replace where old text appears mid-file
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("before\ntarget1\ntarget2\nafter\n")
    p = f.name
r = hl("replace", p, "target1\ntarget2", "REPLACED")
check("multi-line mid-file replace", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("multi-line result order", "before" in content and "REPLACED" in content and "after" in content,
      repr(content))
check("multi-line old removed", "target1" not in content, repr(content))
os.unlink(p)

# 5. Replace with same text (no change)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("same\n")
    p = f.name
r = hl("replace", p, "same", "same")
# same text -> no changes -> exit code 1 with "No changes made" (expected)
check("same text no-change exit", r.returncode != 0, f"code={r.returncode}")
content = open(p, encoding="utf-8").read()
check("same text unchanged", "same" in content, repr(content))
os.unlink(p)

# 6. Replace across non-contiguous lines (negative test -- should fail)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("a\nb\nc\n")
    p = f.name
r = hl("replace", p, "a\nc", "A\nC")
check("non-contiguous should fail", r.returncode != 0, r.stderr[:100])
os.unlink(p)

# 7. Replace at start of file (line 1)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("first\nmiddle\nlast\n")
    p = f.name
r = hl("replace", p, "first", "FIRST")
check("replace at line 1", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("line 1 replaced", content.startswith("FIRST"), repr(content))
os.unlink(p)

# 8. Replace at end of file (no trailing newline in file)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("no trailing newline")
    p = f.name
r = hl("replace", p, "no trailing newline", "WITH NEWLINE\n")
check("EOF no-newline replace", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("EOF result", content.startswith("WITH NEWLINE"), repr(content))
os.unlink(p)

# 9. Replace that only changes middle of a line
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("The quick brown fox\n")
    p = f.name
r = hl("replace", p, "quick brown", "slow red")
check("mid-line partial replace", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("mid-line result", "The slow red fox" in content, repr(content))
os.unlink(p)

# 10. Pipeline: read -> check hashes -> edit -> verify
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
    f.write("line one\nline two\nline three\n")
    p = f.name
r = hl("read", p)
check("pipeline read", r.returncode == 0, r.stderr[:200])
lines = r.stdout.strip().split("\n")
hashes = [line.split("|")[0] for line in lines if "|" in line]
# read shows 4 lines (3 content + 1 empty) but empty line hash isn't needed
check("pipeline hashes >= 2", len(hashes) >= 2, f"got {len(hashes)}")
# Build diff from hashes (first two content lines)
diff = f"= {hashes[0]}..{hashes[1]}\n~REPLACED\n~CONTENT\n"
df = os.path.join(tempfile.gettempdir(), f"pipe_{os.urandom(4).hex()}.txt")
with open(df, "w", encoding="utf-8") as f:
    f.write(diff)
r = hl("edit", p, df)
check("pipeline edit", r.returncode == 0, r.stderr[:200])
content = open(p, encoding="utf-8").read()
check("pipeline result", content.startswith("REPLACED\nCONTENT\nline three"), repr(content))
os.unlink(p)
os.unlink(df)

print(f"\n  [STATS] {total - failed}/{total} passed")
if failed:
    print(f"  [FAIL] {failed} FAILURES")
    sys.exit(1)
else:
    print("  [PASS] ALL PASS")
