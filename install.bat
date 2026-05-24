@echo off
REM OpenCode Tools — Combined installer (Windows cmd)
REM
REM Installs all OpenCode tools (hashline, impact, verify, trace, ...).
REM
REM Usage:
REM   install.bat                  Install from GitHub (default)
REM   install.bat C:\project       Install to specific project
REM   install.bat /local           Install from local repo (no download)
REM   install.bat C:\project /local

setlocal enabledelayedexpansion

set "REPO_BASE=https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main"
set "TOOLS=utils hashline impact verify trace changelog graph lint refactor rename search health snapshot todo tags check audit fmt churn report ghost"
set "LOCAL=0"

REM --- Check flags ---
set "UNINSTALL=0"
for %%a in (%*) do (
    if /I "%%a"=="/local" set "LOCAL=1"
    if /I "%%a"=="-local" set "LOCAL=1"
    if /I "%%a"=="--local" set "LOCAL=1"
    if /I "%%a"=="/uninstall" set "UNINSTALL=1"
    if /I "%%a"=="-uninstall" set "UNINSTALL=1"
    if /I "%%a"=="--uninstall" set "UNINSTALL=1"
)

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
echo   ^|  20 tools for AI-assisted coding         ^|
echo   +------------------------------------------+
echo.
echo   Config: %OPCODE_DIR%
echo   Project: %PROJECT%
echo.

REM --- Uninstall ---
if "%UNINSTALL%"=="1" (
    echo.
    echo   Uninstalling...
    if exist "%OPCODE_DIR%\plugins" rmdir /S /Q "%OPCODE_DIR%\plugins"
    if exist "%PROJECT%\.opencode\plugins" rmdir /S /Q "%PROJECT%\.opencode\plugins"
    for %%t in (%TOOLS%) do (
        if not "%%t"=="utils" (
            set "PYFILE=%%t"
            if "%%t"=="trace" set "PYFILE=calltrace"
            if exist "%PROJECT%\!PYFILE!.py" del /Q "%PROJECT%\!PYFILE!.py"
        )
    )
    echo   Uninstall complete.
    echo.
    exit /b 0
)

REM --- Install plugins ---
if not exist "%OPCODE_DIR%\plugins" mkdir "%OPCODE_DIR%\plugins"

REM --- Copy common.py (shared dependency) ---
if "%LOCAL%"=="1" (
    if exist "%~dp0src\common.py" copy /Y "%~dp0src\common.py" "%OPCODE_DIR%\plugins\common.py" >nul
) else (
    if not exist "%OPCODE_DIR%\plugins\common.py" (
        powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%REPO_BASE%/src/common.py' -OutFile '%OPCODE_DIR%\plugins\common.py' -UseBasicParsing" >nul
    )
)

if "%LOCAL%"=="1" (
    echo   [local mode] copying from "%~dp0"
)
for %%t in (%TOOLS%) do (
    set "TSFILE=%%t"
    if "%%t"=="trace" set "TSFILE=calltrace"
    echo   [%%t] plugin...
    if "%LOCAL%"=="1" (
        if exist "%~dp0plugins\!TSFILE!.ts" (
            copy /Y "%~dp0plugins\!TSFILE!.ts" "%OPCODE_DIR%\plugins\!TSFILE!.ts" >nul
            echo     OK (local)
        ) else (
            echo     SKIP (not found)
        )
    ) else (
        powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%REPO_BASE%/plugins/!TSFILE!.ts' -OutFile '%OPCODE_DIR%\plugins\!TSFILE!.ts' -UseBasicParsing" >nul
        if exist "%OPCODE_DIR%\plugins\!TSFILE!.ts" (
            echo     OK
        ) else (
            echo     FAIL (!TSFILE!.ts — network or server error)
        )
    )
)

REM --- Install to .opencode\plugins (project-local, auto-discovered) ---
if not exist "%PROJECT%\.opencode\plugins" mkdir "%PROJECT%\.opencode\plugins"

REM --- Copy common.py to project-local ---
if not exist "%PROJECT%\.opencode\plugins\common.py" (
    if "%LOCAL%"=="1" (
        if exist "%~dp0src\common.py" copy /Y "%~dp0src\common.py" "%PROJECT%\.opencode\plugins\common.py" >nul
    ) else (
        powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%REPO_BASE%/src/common.py' -OutFile '%PROJECT%\.opencode\plugins\common.py' -UseBasicParsing" >nul
    )
)

for %%t in (%TOOLS%) do (
    set "TSFILE=%%t"
    if "%%t"=="trace" set "TSFILE=calltrace"
    if not exist "%PROJECT%\.opencode\plugins\!TSFILE!.ts" (
        if "%LOCAL%"=="1" (
            if exist "%~dp0plugins\!TSFILE!.ts" copy /Y "%~dp0plugins\!TSFILE!.ts" "%PROJECT%\.opencode\plugins\!TSFILE!.ts" >nul
        ) else (
            powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%REPO_BASE%/plugins/!TSFILE!.ts' -OutFile '%PROJECT%\.opencode\plugins\!TSFILE!.ts' -UseBasicParsing" >nul
        )
    )
)

REM --- Install .py to plugins dir ---
for %%t in (%TOOLS%) do (
    if not "%%t"=="utils" (
        set "PYFILE=%%t"
        if "%%t"=="trace" set "PYFILE=calltrace"
        if not exist "%OPCODE_DIR%\plugins\!PYFILE!.py" (
            if "%LOCAL%"=="1" (
                if exist "%~dp0src\!PYFILE!.py" copy /Y "%~dp0src\!PYFILE!.py" "%OPCODE_DIR%\plugins\!PYFILE!.py" >nul
            ) else (
                powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%REPO_BASE%/src/!PYFILE!.py' -OutFile '%OPCODE_DIR%\plugins\!PYFILE!.py' -UseBasicParsing" >nul
            )
        )
    )
)

REM --- Install engines (project root) ---
for %%t in (%TOOLS%) do (
    if not "%%t"=="utils" (
        set "PYFILE=%%t"
        if "%%t"=="trace" set "PYFILE=calltrace"
        if not exist "%PROJECT%\!PYFILE!.py" (
            echo   [%%t] engine (as !PYFILE!.py)...
            if "%LOCAL%"=="1" (
                if exist "%~dp0src\!PYFILE!.py" (
                    copy /Y "%~dp0src\!PYFILE!.py" "%PROJECT%\!PYFILE!.py" >nul
                    echo     OK (local)
                ) else (
                    echo     SKIP (not found)
                )
            ) else (
                powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%REPO_BASE%/src/!PYFILE!.py' -OutFile '%PROJECT%\!PYFILE!.py' -UseBasicParsing" >nul
                if exist "%PROJECT%\!PYFILE!.py" (
                    echo     OK
                ) else (
                    echo     FAIL (!PYFILE!.py — network or server error)
                )
            )
        ) else (
            echo   [%%t] engine exists
        )
    )
)

REM --- Verify ---
echo.
for %%t in (%TOOLS%) do (
    set "PYFILE=%%t"
    if "%%t"=="trace" set "PYFILE=calltrace"
    if exist "%PROJECT%\!PYFILE!.py" (
        python "%PROJECT%\!PYFILE!.py" --version >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            for /f "tokens=*" %%v in ('python "%PROJECT%\!PYFILE!.py" --version 2^>^&1') do echo   %%t: %%v
        )
    )
)

echo.
echo   Tools installed! Restart OpenCode to activate.
echo.
if exist "%~dp0pyproject.toml" (
    echo   Optional: pip install -e "%~dp0."
    echo   (makes graph, lint, impact, ... available system-wide)
    echo.
)
echo   Test: python %PROJECT%\tests\test_hashline.py
echo.
