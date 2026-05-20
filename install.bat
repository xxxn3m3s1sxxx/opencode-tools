@echo off
REM OpenCode Tools — Combined installer (Windows cmd)
REM
REM Installs all OpenCode tools (hashline, impact, verify, trace, ...).
REM
REM Usage:
REM   install.bat
REM   install.bat C:\atlas

setlocal enabledelayedexpansion

set "REPO_BASE=https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main"
set "TOOLS=utils hashline impact verify trace changelog graph lint refactor rename search"

REM --- Detect OpenCode config dir ---
if defined XDG_CONFIG_HOME (
    set "OPCODE_DIR=%XDG_CONFIG_HOME%\opencode"
) else if defined USERPROFILE (
    set "OPCODE_DIR=%USERPROFILE%\.config\opencode"
) else if defined HOME (
    set "OPCODE_DIR=%HOME%\.config\opencode"
) else (
    set "OPCODE_DIR=%USERPROFILE%\.config\opencode"
)

REM --- Detect project root ---
if not "%1"=="" (
    set "PROJECT=%1"
) else (
    for /f "tokens=*" %%a in ('git rev-parse --show-toplevel 2^>nul') do set "PROJECT=%%a"
    if not defined PROJECT set "PROJECT=%CD%"
)

echo.
echo   +------------------------------------------+
echo   ^|  OpenCode Tools Installer                ^|
echo   ^|  13 tools for AI-assisted coding         ^|
echo   +------------------------------------------+
echo.
echo   Config: %OPCODE_DIR%
echo   Project: %PROJECT%
echo.

REM --- Install plugins ---
if not exist "%OPCODE_DIR%\plugins" mkdir "%OPCODE_DIR%\plugins"

for %%t in (%TOOLS%) do (
    echo   [%%t] plugin...
    powershell -Command "Invoke-WebRequest -Uri '%REPO_BASE%/%%t.ts' -OutFile '%OPCODE_DIR%\plugins\%%t.ts' -UseBasicParsing -ErrorAction SilentlyContinue" >nul 2>&1
    if exist "%OPCODE_DIR%\plugins\%%t.ts" (
        echo     OK
    ) else (
        echo     SKIP (download failed)
    )
)

REM --- Install .py to plugins dir ---
for %%t in (%TOOLS%) do (
    if not "%%t"=="utils" (
        if not exist "%OPCODE_DIR%\plugins\%%t.py" (
            powershell -Command "Invoke-WebRequest -Uri '%REPO_BASE%/%%t.py' -OutFile '%OPCODE_DIR%\plugins\%%t.py' -UseBasicParsing -ErrorAction SilentlyContinue" >nul 2>&1
        )
    )
)

REM --- Install engines (project root) ---
for %%t in (%TOOLS%) do (
    if not "%%t"=="utils" (
        if not exist "%PROJECT%\%%t.py" (
            echo   [%%t] engine...
            powershell -Command "Invoke-WebRequest -Uri '%REPO_BASE%/%%t.py' -OutFile '%PROJECT%\%%t.py' -UseBasicParsing -ErrorAction SilentlyContinue" >nul 2>&1
            if exist "%PROJECT%\%%t.py" (
                echo     OK
            ) else (
                echo     SKIP (download failed)
            )
        ) else (
            echo   [%%t] engine exists
        )
    )
)

REM --- Verify ---
echo.
for %%t in (%TOOLS%) do (
    if exist "%PROJECT%\%%t.py" (
        python "%PROJECT%\%%t.py" --version >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            for /f "tokens=*" %%v in ('python "%PROJECT%\%%t.py" --version 2^>^&1') do echo   %%t: %%v
        )
    )
)

echo.
echo   Tools installed! Restart OpenCode to activate.
echo.
echo   Test: python %%PROJECT%%\test_hashline.py
echo.
