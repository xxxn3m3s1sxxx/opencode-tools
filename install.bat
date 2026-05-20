@echo off
REM OpenCode Tools — Windows cmd installer
REM hashline + impact + verify + trace
REM
REM Usage:
REM   install.bat
REM   install.bat "C:\path\to\project"

setlocal enabledelayedexpansion

set REPO=https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main
set TOOLS=hashline impact verify trace

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
echo  ^|  hashline + impact + verify + trace      ^|
echo  +------------------------------------------+
echo.
echo  Config: %OPDIR%
echo  Project: %PROJ%
echo.

REM Create plugins dir
if not exist "%OPDIR%\plugins\" mkdir "%OPDIR%\plugins"

REM Install plugins (TS files)
for %%t in (%TOOLS%) do (
    if exist "%%t.ts" (
        copy /Y "%%t.ts" "%OPDIR%\plugins\%%t.ts" >nul
        echo  [%%t] plugin -^> %OPDIR%\plugins\%%t.ts
    ) else (
        echo  [%%t] plugin -^> downloading...
        powershell -Command "Invoke-WebRequest -Uri '%REPO%/%%t.ts' -OutFile '%OPDIR%\plugins\%%t.ts'" >nul 2>&1
    )
)

REM Install engines (PY files)
for %%t in (%TOOLS%) do (
    if exist "%%t.py" (
        copy /Y "%%t.py" "%PROJ%\%%t.py" >nul
        echo  [%%t] engine -^> %PROJ%\%%t.py
    ) else if not exist "%PROJ%\%%t.py" (
        echo  [%%t] engine -^> downloading...
        powershell -Command "Invoke-WebRequest -Uri '%REPO%/%%t.py' -OutFile '%PROJ%\%%t.py'" >nul 2>&1
    ) else (
        echo  [%%t] engine -^> %PROJ%\%%t.py (exists)
    )
)

REM Verify
echo.
for %%t in (%TOOLS%) do (
    python "%PROJ%\%%t.py" --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%v in ('python "%PROJ%\%%t.py" --version 2^>^&1') do echo  %%v
    ) else (
        echo  [WARN] %%t: verification failed
    )
)

echo.
echo  Tools installed! Restart OpenCode to activate.
echo.
echo  Test:
echo    python %PROJ%\hashline.py --version
echo.
