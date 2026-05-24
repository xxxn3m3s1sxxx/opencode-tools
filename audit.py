#!/usr/bin/env python3
"""audit — secret scanner. Find API keys, passwords, tokens, private keys.

Usage:
  audit                           Scan current directory
  audit --root <dir>              Scan specific directory
  audit --json                    JSON output
  audit --quiet                   Only show secrets, no header/footer
  audit --allowlist <file>        File with allowed patterns (one per line)
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from common import VERSION, EXCLUDE_DIRS, reconfigure_stdout_stderr

reconfigure_stdout_stderr()

HIGH_SEVERITY: list[tuple[str, str, str]] = [
    ("aws-key", r"(?i)AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (
        "aws-secret",
        r"(?i)aws[_-]?secret[_-]?access[_-]?key.{0,30}(?P<value>[A-Za-z0-9/+=]{40})",
        "AWS Secret Access Key",
    ),
    ("github-token", r"(?i)gh[pousr]_[A-Za-z0-9_]{36,255}", "GitHub Token"),
    ("github-old", r"(?i)[a-f0-9]{40}(?=\s|$|\"|')", "GitHub 40-char hex (possible token)"),
    ("slack-token", r"(?i)xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}", "Slack Token"),
    ("slack-webhook", r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{44}", "Slack Webhook"),
    ("google-api", r"(?i)AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
    ("ssh-private-key", r"-----BEGIN\s?(RSA|DSA|EC|OPENSSH|PRIVATE)\s?KEY-----", "SSH Private Key"),
    ("pgp-private-key", r"-----BEGIN PGP PRIVATE KEY BLOCK-----", "PGP Private Key"),
    ("jwt-token", r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT Token"),
    (
        "generic-secret",
        r"(?i)(secret|password|token|apikey|api_key|auth)[\s:=]+\"?(?P<value>[A-Za-z0-9_\-\./@+=]{16,64})\"?",
        "Generic Secret",
    ),
    ("generic-token", r"(?i)(token|api_key)[\s:=]+['\"](?P<value>[A-Za-z0-9_\-]{20,})['\"]", "Generic Token"),
    ("private-key-path", r"(?i)id_rsa|id_ecdsa|id_ed25519|id_dsa(?!\.pub)", "Private Key File Reference"),
    ("npm-token", r"(?i)npm_[A-Za-z0-9]{36}", "npm Token"),
    ("pypi-token", r"(?i)pypi[-_]?[Aa]pi[-_]?[Tt]oken.{0,30}(?P<value>[A-Za-z0-9_\-]{20,})", "PyPI Token"),
    (
        "heroku-api",
        r"(?i)[hH][eE][rR][oO][kK][uU].{0,30}[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}",
        "Heroku API Key",
    ),
    ("stripe-live", r"(?i)sk_live_[0-9a-zA-Z]{24,}", "Stripe Live Secret Key"),
    ("stripe-test", r"(?i)sk_test_[0-9a-zA-Z]{24,}", "Stripe Test Secret Key"),
    ("twilio", r"(?i)SK[0-9a-fA-F]{32}", "Twilio API Key"),
    ("docker-config", r"(?i)auths\s*\{", "Docker config auth entry"),
]

MEDIUM_SEVERITY: list[tuple[str, str, str]] = [
    ("connection-string", r"(?i)(connection\s*string|connstr)[\s:=]+['\"](?P<value>.{20,})['\"]", "Connection String"),
    ("basic-auth-url", r"https?://[^:]+:[^@]+@", "Basic Auth in URL"),
    ("s3-endpoint", r"(?i)https?://s3[.\-].*\.amazonaws\.com", "S3 Endpoint URL"),
    ("pg-connection", r"postgres(ql)?://[^:]+:[^@]+@", "PostgreSQL Connection String"),
    ("redis-connection", r"redis://[^:]+:[^@]+@", "Redis Connection String"),
    ("mongo-connection", r"mongodb(\+srv)?://[^:]+:[^@]+@", "MongoDB Connection String"),
    ("mysql-connection", r"mysql://[^:]+:[^@]+@", "MySQL Connection String"),
    ("authorization-header", r"(?i)(Authorization|Bearer)\s+[A-Za-z0-9_\-\.]{20,}", "Authorization Header Value"),
    ("x-api-key-header", r"(?i)x-api-key\s*:?\s*['\"]?(?P<value>[A-Za-z0-9]{20,})['\"]?", "X-API-Key Header"),
    ("ssh-key-path", r"(?i)~/.ssh/", "SSH Key Path Reference"),
    ("aws-config-ref", r"(?i)~/.aws/credentials", "AWS Credentials File Reference"),
]

LOW_SEVERITY: list[tuple[str, str, str]] = [
    (".env-ref", r"\.env", ".env file reference"),
    ("password-field", r"(?i)(password|passwd|pwd)\s*[:=]\s*(?!['\"]?\*|['\"]?x)", "Password field assignment"),
    ("secret-field", r"(?i)(secret)\s*[:=]\s*(?!['\"]?\*|['\"]?x)", "Secret field assignment"),
    ("api-key-field", r"(?i)(api[-_]?key|apikey)\s*[:=]\s*(?!['\"]?\*|['\"]?x)", "API key field assignment"),
    ("token-field", r"(?i)(token)\s*[:=]\s*(?!['\"]?\*|['\"]?x)", "Token field assignment"),
    ("private-key-path", r"(?i)private_key|privkey", "Private key file reference"),
    ("certificate", r"-----BEGIN CERTIFICATE-----", "Certificate content"),
]


def _load_allowlist(path: str) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(re.compile(line, re.IGNORECASE))
    except FileNotFoundError:
        pass
    return patterns


def _is_allowlisted(line: str, allowlist: list[re.Pattern[str]]) -> bool:
    for p in allowlist:
        if p.search(line):
            return True
    a = "AKIA" in line and "EXAMPLE" in line
    return a


def _walk(root: str) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if _is_binary(fp) or os.path.getsize(fp) > 1_000_000:
                continue
            files.append(fp)
    return sorted(files)


_BINARY_EXTS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".zip",
    ".gz",
    ".bz2",
    ".xz",
    ".tar",
    ".7z",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".pyc",
    ".pyo",
    ".pyd",
    ".o",
    ".obj",
    ".lib",
    ".dll",
    ".so",
    ".dylib",
    ".exe",
    ".msi",
    ".deb",
    ".rpm",
    ".lock",
    ".sum",
    ".sig",
}


def _is_binary(fp: str) -> bool:
    _, ext = os.path.splitext(fp)
    return ext.lower() in _BINARY_EXTS


def scan_file(
    fp: str,
    root_len: int,
    allowlist: list[re.Pattern[str]],
    rules: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        with open(fp, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return findings

    for i, line in enumerate(lines, 1):
        stripped = line.rstrip("\n\r")
        if _is_allowlisted(stripped, allowlist):
            continue
        for rule_id, pattern, description in rules:
            m = re.search(pattern, stripped)
            if m:
                value = m.group(0)
                if len(value) > 80:
                    value = value[:40] + "..." + value[-37:]
                findings.append(
                    {
                        "file": fp[root_len:],
                        "line": i,
                        "rule": rule_id,
                        "description": description,
                        "value": value,
                    }
                )
                break
    return findings


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"audit.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    root = os.getcwd()
    use_json = "--json" in args
    quiet = "--quiet" in args
    allowlist_file = ""

    for a in args:
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--root":
            idx = args.index(a) + 1
            if idx < len(args):
                root = args[idx]
        elif a.startswith("--allowlist="):
            allowlist_file = a.split("=", 1)[1]
        elif a == "--allowlist":
            idx = args.index(a) + 1
            if idx < len(args):
                allowlist_file = args[idx]

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    allowlist = _load_allowlist(allowlist_file) if allowlist_file else []
    root_len = len(root.rstrip("/\\")) + 1
    files = _walk(root)
    all_findings: list[dict[str, Any]] = []
    severities: dict[str, list[tuple[str, str, str]]] = {
        "high": HIGH_SEVERITY,
        "medium": MEDIUM_SEVERITY,
        "low": LOW_SEVERITY,
    }

    for fp in files:
        for sev, rules in severities.items():
            for finding in scan_file(fp, root_len, allowlist, rules):
                finding["severity"] = sev
                all_findings.append(finding)

    high = sum(1 for f in all_findings if f["severity"] == "high")
    medium = sum(1 for f in all_findings if f["severity"] == "medium")
    low = sum(1 for f in all_findings if f["severity"] == "low")

    if use_json:
        print(
            json.dumps(
                {
                    "status": "ok" if high == 0 else "alert",
                    "total": len(all_findings),
                    "high": high,
                    "medium": medium,
                    "low": low,
                    "findings": all_findings,
                },
                indent=2,
            )
        )
    elif quiet:
        for f in all_findings:
            sev_icon = "!!!" if f["severity"] == "high" else ("!!" if f["severity"] == "medium" else "!")
            print(f"{sev_icon} {f['file']}:{f['line']}  [{f['severity']}] {f['description']}  {f['value']}")
    else:
        if all_findings:
            sev_label = {"high": "HIGH", "medium": "MED", "low": "LOW"}
            for f in all_findings:
                sev_tag = sev_label[f["severity"]]
                print(f"  [{sev_tag}] {f['file']}:{f['line']}  {f['description']}")
                print(f"          {f['value']}")
            print()
            print(f"Findings: {len(all_findings)} total ({high} high, {medium} medium, {low} low)")
        else:
            print("audit: No secrets found ✨")
        print(f"Scanned: {len(files)} files in {root}")

    return 0 if high == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
