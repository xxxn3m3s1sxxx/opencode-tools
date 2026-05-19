#!/usr/bin/env python3
"""Deeper edge case tests for hashline.py."""
import os
import subprocess
import sys
import tempfile

HL = os.path.join(os.path.dirname(__file__), "..", "..", "hashline.py")
if not os.path.exists(HL):
    HL = os.path.join(os.path.dirname(__file__), "hashline.py")
P = sys.executable
fail = 0
total = 0


def chk(desc, cond, msg=""):
    global total, fail
    total += 1
    if cond:
        print(f"  \u2705 {desc}")
    else:
        print(f"  \u274c {desc}  {msg}")
        fail += 1


def hl(*args, **kw):
    return subprocess.run(
        [P, HL] + list(args),
        capture_output=True, text=True, encoding="utf-8", timeout=15, **kw
    )


# 1. Multi-line partial: leading on line 1, trailing on line 2
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("prefix TARGET\ntrailing suffix\n")
    p = fp.name
r = hl("replace", p, "TARGET\ntrailing", "REPLACED")
chk("multi-line partial leading+trailing", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("multi-line partial result", "prefix REPLACED suffix" in c, repr(c))
os.unlink(p)

# 2. cmd_edit with multiple @@ sections edits one file
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("a\nb\n")
    p1 = fp.name
tmpdir = tempfile.gettempdir()
df = os.path.join(tmpdir, f"multi_{os.urandom(4).hex()}.txt")
r1 = hl("check", p1)
h1 = r1.stdout.strip().split("\n")[0]
h2 = r1.stdout.strip().split("\n")[1]
with open(df, "w", encoding="utf-8") as f:
    f.write(f"@@ {p1}\n= {h1}..{h1}\n~A\n= {h2}..{h2}\n~B\n")
r = hl("edit", p1, df)
chk("multi-section edit exit", r.returncode == 0, r.stderr[:200])
c1 = open(p1, encoding="utf-8").read()
chk("multi-section file1", "A" in c1 and "B" in c1, repr(c1))
os.unlink(p1)
os.unlink(df)

# 3. Single-char file
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("Z")
    p = fp.name
r = hl("read", p)
chk("single-char read", r.returncode == 0, r.stderr[:200])
r = hl("replace", p, "Z", "A")
chk("single-char replace", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("single-char result", c == "A", repr(c))
os.unlink(p)

# 4. File with only newlines
with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as fp:
    fp.write(b"\n\n\n")
    p = fp.name
r = hl("read", p)
chk("newlines-only read", r.returncode == 0, r.stderr[:200])
r = hl("replace", p, "", "INSERT")
chk("newlines-only replace empty", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("newlines-only result", "INSERT" in c, repr(c[:100]))
os.unlink(p)

# 5. Match at EOF (no trailing newline after match)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("line1\nline2\nMATCH AT END")
    p = fp.name
r = hl("replace", p, "MATCH AT END", "REPLACED")
chk("EOF partial match", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("EOF partial result", c.strip().endswith("REPLACED"), repr(c))
os.unlink(p)

# 6. Match at BOF (no leading on line 1)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("MATCH HERE\nline2\n")
    p = fp.name
r = hl("replace", p, "MATCH HERE", "REPLACED")
chk("BOF match no leading", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("BOF match result", c.startswith("REPLACED"), repr(c))
os.unlink(p)

# 7. UTF-8 multi-byte in replacement
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("hello\n")
    p = fp.name
r = hl("replace", p, "hello", "h\u00e9llo w\u00f6rld \U0001f389")
chk("multi-byte UTF-8 replacement", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("multi-byte UTF-8 result", "h\u00e9llo w\u00f6rld \U0001f389" in c, repr(c))
os.unlink(p)

# 8. Replace where text appears multiple times in the same line
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("foo bar foo\n")
    p = fp.name
r = hl("replace", p, "bar", "baz")
chk("mid-line repeated context", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("mid-line repeated result", "foo baz foo" in c, repr(c))
os.unlink(p)

# 9. Leading whitespace preserved
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("    indented line\n")
    p = fp.name
r = hl("replace", p, "indented", "FIXED")
chk("leading whitespace preserved", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("leading WS result", "    FIXED line" in c, repr(c))
os.unlink(p)

# 10. Multiple replacements to same file (sequentially shift lines)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("a\nb\nc\nd\n")
    p = fp.name
for old, new in [("a\nb", "AB"), ("c\nd", "CD")]:
    r = hl("replace", p, old, new)
    chk(f"shift seq {old}->{new}", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("shift seq result", c.strip() == "AB\nCD", repr(c))
os.unlink(p)

# 11. Replace where leading/trailing contain tabs (not stripped)
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as fp:
    fp.write("\t\tTARGET\t\t\n")
    p = fp.name
r = hl("replace", p, "TARGET", "REPLACED")
chk("tabs in leading/trailing", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8").read()
chk("tabs result", "\t\tREPLACED\t\t" in c, repr(c))
os.unlink(p)

# 12. match_text appears after BOM in content
with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as fp:
    fp.write(b"\xef\xbb\xbfhello\n")
    p = fp.name
r = hl("replace", p, "hello", "HELLO")
chk("BOM file replace", r.returncode == 0, r.stderr[:200])
c = open(p, encoding="utf-8-sig").read()
chk("BOM result", "HELLO" in c, repr(c))
os.unlink(p)

print(f"\n  \U0001f4ca {total - fail}/{total} passed")
if fail:
    print(f"  \u274c {fail} FAILURES")
    sys.exit(1)
else:
    print("  \U0001f389 ALL PASS")
