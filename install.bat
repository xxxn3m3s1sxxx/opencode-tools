@echo off
REM OpenCode Tools — Windows cmd installer
REM 13 plugins + engines — edit, impact, verify, trace, rename, graph, changelog, search, lint, refactor
REM
REM Usage:
REM   install.bat
REM   install.bat "C:\path\to\project"

setlocal enabledelayedexpansion

set REPO=https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main
set TOOLS=utils hashline impact verify trace rename graph changelog search lint refactor

REM Detect OpenCode config dir
if defined XDG_CONFIG_HOME (
    set OPDIR=%XDG_CONFIG_HOME%\opencode
) else if defined HOME (
    set OPDIR=%HOME%\.config\opencode
) else (
    set OPDIR=%USERPROFILE%\.config\opencode
)

REM Detect project root
if "%~1"=="" (
    for /f "delims=" %%i in ('git rev-parse --show-toplevel 2^>nul') do set PROJ=%%i
    if not defined PROJ set PROJ=%CD%
) else (
    set PROJ=%~1
)

echo.
echo  +------------------------------------------+
echo  ^|  OpenCode Tools Installer                ^|
echo  ^|  13 plugins + engines                    ^|
echo  +------------------------------------------+
echo.
echo  Config: %OPDIR%
echo  Project: %PROJ%
echo.

if not exist "%OPDIR%\plugins\" mkdir "%OPDIR%\plugins"

REM Install plugins (TS files)
for %%t in (%TOOLS%) do (
    if exist "%%t.ts" (
        copy /Y "%%t.ts" "%OPDIR%\plugins\%%t.ts" >nul
        echo  [plugin] %%t -^> %OPDIR%\plugins\%%t.ts (local)
    ) else (
        echo  [plugin] %%t -^> downloading...
        powershell -Command "Invoke-WebRequest -Uri '%REPO%/%%t.ts' -OutFile '%OPDIR%\plugins\%%t.ts'" >nul 2>&1
        if exist "%OPDIR%\plugins\%%t.ts" (
            echo  [plugin] %%t -^> downloaded
        ) else (
            echo  [WARN] %%t download failed
        )
    )
)

REM Install engines (PY files)
for %%t in (hashline impact verify trace rename graph changelog search lint refactor) do (
    set "ENGINE_DEST=%PROJ%\%%t.py"
    if exist "%%t.py" (
        copy /Y "%%t.py" "!ENGINE_DEST!" >nul
        echo  [engine] %%t -^> !ENGINE_DEST! (local)
    ) else if not exist "!ENGINE_DEST!" (
        echo  [engine] %%t -^> downloading...
        powershell -Command "Invoke-WebRequest -Uri '%REPO%/%%t.py' -OutFile '!ENGINE_DEST!'" >nul 2>&1
        if exist "!ENGINE_DEST!" (
            echo  [engine] %%t -^> downloaded
        ) else (
            echo  [WARN] %%t download failed
        )
    ) else (
        echo  [engine] %%t -^> !ENGINE_DEST! (exists)
    )
)

REM Verify
echo.
for %%t in (hashline impact verify trace rename graph changelog search lint refactor) do (
    python "%PROJ%\%%t.py" --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%v in ('python "%PROJ%\%%t.py" --version 2^>^&1') do echo  %%v
    ) else (
        echo  [WARN] %%t: verify failed
    )
)

echo.
echo  Tools installed! Restart OpenCode to activate.
echo.
