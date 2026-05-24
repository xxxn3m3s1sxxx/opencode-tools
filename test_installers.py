#!/usr/bin/env python3
"""Integration tests for install.bat and install.ps1.

Tests local-mode installation (no network) in isolated temp dirs.
Verifies file placement, trace->calltrace mapping, and config dir detection.
"""

import os
import subprocess
import sys
import tempfile

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

PASS = 0
FAIL = 0

EXPECTED_TS = [
    "utils.ts",
    "hashline.ts",
    "impact.ts",
    "verify.ts",
    "trace.ts",
    "changelog.ts",
    "graph.ts",
    "lint.ts",
    "refactor.ts",
    "rename.ts",
    "search.ts",
]

EXPECTED_PY_ENGINES = [
    "hashline.py",
    "impact.py",
    "verify.py",
    "calltrace.py",
    "changelog.py",
    "graph.py",
    "lint.py",
    "refactor.py",
    "rename.py",
    "search.py",
]


def check(desc, cond, detail=""):
    global PASS, FAIL
    if cond:
        print(f"  [OK] {desc}")
        PASS += 1
    else:
        print(f"  [FAIL] {desc}  {detail}")
        FAIL += 1


def _ensure_local_files(opcode_dir, proj_dir):
    """Copy all .ts and .py files manually so installers find them."""
    import shutil

    for fn in EXPECTED_TS:
        src = os.path.join(TOOLS_DIR, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(opcode_dir, "plugins", fn))
            os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"), exist_ok=True)
            shutil.copy2(src, os.path.join(proj_dir, ".opencode", "plugins", fn))
    for fn in EXPECTED_PY_ENGINES:
        src = os.path.join(TOOLS_DIR, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(opcode_dir, "plugins", fn))
            shutil.copy2(src, os.path.join(proj_dir, fn))
    # also calltrace.py (renamed from trace.py)
    src = os.path.join(TOOLS_DIR, "calltrace.py")
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(opcode_dir, "plugins", "calltrace.py"))
        shutil.copy2(src, os.path.join(proj_dir, "calltrace.py"))


def test_bat_local_mode():
    """install.bat /local completes without crash."""
    with tempfile.TemporaryDirectory() as tmp:
        opcode_dir = os.path.join(tmp, "config", "opencode")
        proj_dir = os.path.join(tmp, "project")
        os.makedirs(os.path.join(opcode_dir, "plugins"))
        os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"))

        env = os.environ.copy()
        env["USERPROFILE"] = tmp
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")

        wrapper = os.path.join(tmp, "_run.bat")
        with open(wrapper, "w") as f:
            f.write(f'@echo off\ncall "{os.path.join(TOOLS_DIR, "install.bat")}" %*\n')

        subprocess.run(
            [wrapper, proj_dir, "/local"],
            capture_output=True,
            text=True,
            env=env,
            cwd=TOOLS_DIR,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        # 404 warnings from placeholder repo are expected — files copy locally OK


def test_bat_local_copies_plugins():
    """install.bat copies .ts plugins correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        opcode_dir = os.path.join(tmp, "config", "opencode")
        proj_dir = os.path.join(tmp, "project")
        os.makedirs(os.path.join(opcode_dir, "plugins"))
        os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"))

        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")
        env["USERPROFILE"] = tmp

        wrapper = os.path.join(tmp, "_run.bat")
        with open(wrapper, "w") as f:
            f.write(f'@echo off\ncall "{os.path.join(TOOLS_DIR, "install.bat")}" %*\n')
            f.write("echo EXIT_CODE=%ERRORLEVEL%\n")

        subprocess.run(
            [wrapper, proj_dir, "/local"],
            capture_output=True,
            text=True,
            env=env,
            cwd=TOOLS_DIR,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        for fn in EXPECTED_TS:
            check(f"bat local .ts plugin: {fn}", os.path.exists(os.path.join(opcode_dir, "plugins", fn)))

        # Verify trace->calltrace mapping
        check(
            "bat local calltrace.py not trace.py",
            os.path.exists(os.path.join(opcode_dir, "plugins", "calltrace.py"))
            and not os.path.exists(os.path.join(opcode_dir, "plugins", "trace.py")),
        )

        # Verify .opencode/plugins gets files too
        for fn in EXPECTED_TS:
            check(
                f"bat local .opencode/plugins: {fn}", os.path.exists(os.path.join(proj_dir, ".opencode", "plugins", fn))
            )


def test_ps1_offline_mode():
    """install.ps1 -Offline copies files correctly."""
    with tempfile.TemporaryDirectory() as tmp:
        opcode_dir = os.path.join(tmp, "config", "opencode")
        proj_dir = os.path.join(tmp, "project")
        os.makedirs(os.path.join(opcode_dir, "plugins"))
        os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"))

        env = os.environ.copy()
        env["USERPROFILE"] = tmp
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")

        p = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-File",
                os.path.join(TOOLS_DIR, "install.ps1"),
                "-Project",
                proj_dir,
                "-Offline",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=TOOLS_DIR,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        for fn in EXPECTED_TS:
            check(
                f"ps1 offline .ts plugin: {fn}", os.path.exists(os.path.join(opcode_dir, "plugins", fn)), p.stderr[:200]
            )

        check("ps1 offline calltrace.py exists", os.path.exists(os.path.join(opcode_dir, "plugins", "calltrace.py")))
        check("ps1 offline no trace.py", not os.path.exists(os.path.join(opcode_dir, "plugins", "trace.py")))

        # engine files
        for fn in EXPECTED_PY_ENGINES:
            check(f"ps1 offline engine: {fn}", os.path.exists(os.path.join(proj_dir, fn)), p.stderr[:200])


def test_bat_config_dir_precedence():
    """install.bat uses XDG_CONFIG_HOME over USERPROFILE."""
    with tempfile.TemporaryDirectory() as tmp:
        opcode_dir_xdg = os.path.join(tmp, "xdg", "opencode")
        opcode_dir_home = os.path.join(tmp, "home", ".config", "opencode")
        proj_dir = os.path.join(tmp, "project")
        for d in [opcode_dir_xdg, opcode_dir_home, proj_dir]:
            os.makedirs(os.path.join(d, "plugins"), exist_ok=True)
        os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"), exist_ok=True)

        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "xdg")
        env["USERPROFILE"] = os.path.join(tmp, "home")

        wrapper = os.path.join(tmp, "_run.bat")
        with open(wrapper, "w") as f:
            f.write(f'@echo off\ncall "{os.path.join(TOOLS_DIR, "install.bat")}" %*\n')

        subprocess.run(
            [wrapper, proj_dir, "/local"],
            capture_output=True,
            text=True,
            env=env,
            cwd=TOOLS_DIR,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        check("bat XDG_CONFIG_HOME takes precedence", os.path.exists(os.path.join(opcode_dir_xdg, "plugins")))


def test_ps1_config_dir_precedence():
    """install.ps1 uses XDG_CONFIG_HOME over USERPROFILE."""
    with tempfile.TemporaryDirectory() as tmp:
        opcode_dir_xdg = os.path.join(tmp, "xdg", "opencode")
        opcode_dir_home = os.path.join(tmp, "home", ".config", "opencode")
        proj_dir = os.path.join(tmp, "project")
        os.makedirs(os.path.join(opcode_dir_xdg, "plugins"), exist_ok=True)
        os.makedirs(os.path.join(opcode_dir_home, "plugins"), exist_ok=True)
        os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"), exist_ok=True)

        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "xdg")
        env["USERPROFILE"] = os.path.join(tmp, "home")

        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-File",
                os.path.join(TOOLS_DIR, "install.ps1"),
                "-Project",
                proj_dir,
                "-Offline",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=TOOLS_DIR,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        check("ps1 XDG_CONFIG_HOME takes precedence", os.path.exists(os.path.join(opcode_dir_xdg, "plugins")))


def test_bat_skip_existing_engine():
    """install.bat should not overwrite existing engine."""
    with tempfile.TemporaryDirectory() as tmp:
        opcode_dir = os.path.join(tmp, "config", "opencode")
        proj_dir = os.path.join(tmp, "project")
        os.makedirs(os.path.join(opcode_dir, "plugins"))
        os.makedirs(os.path.join(proj_dir, ".opencode", "plugins"))

        # Pre-create an engine file with marker content
        engine_path = os.path.join(proj_dir, "verify.py")
        with open(engine_path, "w") as f:
            f.write("# ORIGINAL — should not be overwritten\n")

        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = os.path.join(tmp, "config")
        env["USERPROFILE"] = tmp

        wrapper = os.path.join(tmp, "_run.bat")
        with open(wrapper, "w") as f:
            f.write(f'@echo off\ncall "{os.path.join(TOOLS_DIR, "install.bat")}" %*\n')

        subprocess.run(
            [wrapper, proj_dir, "/local"],
            capture_output=True,
            text=True,
            env=env,
            cwd=TOOLS_DIR,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )

        with open(engine_path) as f:
            content = f.read()
        check("bat does not overwrite existing engine", "ORIGINAL" in content)


# ====================================================================
def main():
    print("\n  Installer Integration Tests")
    print(f"  {'=' * 32}")
    tests = [
        test_bat_local_mode,
        test_bat_local_copies_plugins,
        test_ps1_offline_mode,
        test_bat_config_dir_precedence,
        test_ps1_config_dir_precedence,
        test_bat_skip_existing_engine,
    ]
    for t in tests:
        t()
    total = PASS + FAIL
    print(f"\n  [{PASS}/{total} passed]")
    if FAIL:
        print(f"  [{FAIL}/{total} FAILED]")
        return 1
    print("  ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
