#!/usr/bin/env python3
"""report — project health report. Combine check + audit + fmt + churn + health.

Usage:
  report                          Full report (markdown)
  report --quick                  Skip slow checks (tests, full audit)
  report --json                   JSON output
  report --output <file>          Write report to file
  report --root <dir>             Run in specific directory
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

from common import VERSION, reconfigure_stdout_stderr

reconfigure_stdout_stderr()


def _run_tool(tool: str, args: list[str], root: str, timeout: int = 120) -> dict[str, Any]:
    start = time.time()
    py = (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{tool}.py")
        if tool != "health"
        else os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{tool}.py")
    )
    try:
        r = subprocess.run(
            [sys.executable, py] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=root,
        )
        elapsed = round(time.time() - start, 2)
        return {
            "tool": tool,
            "status": "ok" if r.returncode == 0 else "fail",
            "exit_code": r.returncode,
            "elapsed": elapsed,
            "output": r.stdout.strip(),
        }
    except FileNotFoundError:
        return {"tool": tool, "status": "error", "exit_code": -1, "elapsed": 0, "output": "tool not found"}
    except subprocess.TimeoutExpired:
        return {
            "tool": tool,
            "status": "error",
            "exit_code": -1,
            "elapsed": round(time.time() - start, 2),
            "output": "timed out",
        }


def _parse_health_json(output: str) -> dict[str, Any]:
    import re

    metrics: dict[str, Any] = {}
    m = re.search(r"(\d+) source files", output)
    if m:
        metrics["files"] = int(m.group(1))
    m = re.search(r"(\d+) lines of code", output)
    if m:
        metrics["lines"] = int(m.group(1))
    return metrics


def _parse_churn(output: str) -> int:
    m = __import__("re").search(r"Total: (\d+) files", output)
    return int(m.group(1)) if m else 0


def _parse_audit(output: str) -> dict[str, int]:
    import re

    counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "total": 0}
    m = re.search(r"Findings: (\d+) total \((\d+) high, (\d+) medium, (\d+) low\)", output)
    if m:
        counts["total"] = int(m.group(1))
        counts["high"] = int(m.group(2))
        counts["medium"] = int(m.group(3))
        counts["low"] = int(m.group(4))
    return counts


def _fmt_time(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def generate_markdown(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append("# Project Health Report")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Version: {VERSION}")
    lines.append("")

    total_elapsed = sum(r["elapsed"] for r in results)
    all_ok = all(r["status"] == "ok" for r in results)
    lines.append(
        f"**Overall: {'✅ PASS' if all_ok else '❌ FAIL'}** — {len(results)} checks in {_fmt_time(total_elapsed)}"
    )
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Tool | Status | Time |")
    lines.append("|------|--------|------|")
    for r in results:
        icon = {"ok": "✅", "fail": "❌", "error": "⚠️"}.get(r["status"], "❓")
        lines.append(f"| {r['tool']} | {icon} {r['status']} | {_fmt_time(r['elapsed'])} |")

    lines.append("")
    lines.append("## Details")
    lines.append("")

    for r in results:
        if r["status"] != "ok" and r["output"]:
            lines.append(f"### {r['tool']} — FAIL")
            lines.append("")
            lines.append("```")
            lines.append(r["output"][:2000])
            lines.append("```")
            lines.append("")

    all_outputs = {r["tool"]: r["output"] for r in results}

    if "health" in all_outputs:
        metrics = _parse_health_json(all_outputs["health"])
        if metrics:
            lines.append("### Code Metrics")
            lines.append("")
            lines.append(f"- **Files:** {metrics.get('files', '?')}")
            lines.append(f"- **Lines:** {metrics.get('lines', '?')}")
            lines.append("")

    if "audit" in all_outputs:
        findings = _parse_audit(all_outputs["audit"])
        if findings["total"] > 0:
            lines.append("### Secret Scan Findings")
            lines.append("")
            lines.append(f"- **High:** {findings['high']}")
            lines.append(f"- **Medium:** {findings['medium']}")
            lines.append(f"- **Low:** {findings['low']}")
            lines.append(f"- **Total:** {findings['total']}")
            lines.append("")

    if "churn" in all_outputs:
        total = _parse_churn(all_outputs["churn"])
        if total:
            lines.append("### Git Churn")
            lines.append("")
            lines.append(f"- **High-churn files:** {total}")
            lines.append("")

    if "fmt" in all_outputs:
        status = (
            "✅ Formatted" if all_outputs.get("fmt") and "ok" in str(all_outputs["fmt"]).lower() else "❌ Unformatted"
        )
        lines.append(f"### Formatting: {status}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"report.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    root = os.getcwd()
    use_json = "--json" in args
    quick = "--quick" in args
    output_file = ""

    for a in args:
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--root":
            idx = args.index(a) + 1
            if idx < len(args):
                root = args[idx]
        elif a.startswith("--output="):
            output_file = a.split("=", 1)[1]
        elif a == "--output":
            idx = args.index(a) + 1
            if idx < len(args):
                output_file = args[idx]

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []
    results.append(_run_tool("health", ["--quick"], root, 30))

    if not quick:
        results.append(_run_tool("check", ["--quick"], root, 180))
        results.append(_run_tool("audit", ["--quiet", "."], root, 60))
        results.append(_run_tool("churn", ["--min-commits", "1"], root, 30))
        results.append(_run_tool("fmt", ["--ruff", "--check"], root, 60))
    else:
        results.append(_run_tool("audit", ["--quiet", "--root", root], root, 30))

    if use_json:
        print(json.dumps({"results": results, "count": len(results)}, indent=2))
    else:
        report = generate_markdown(results)
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"report written to {output_file}")
        else:
            print(report)

    all_ok = all(r["status"] == "ok" for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
