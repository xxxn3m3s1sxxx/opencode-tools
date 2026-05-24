# OpenCode Tools — Combined installer (PowerShell)
#
# Installs all OpenCode tools (20 plugins + engines) in one command.
# Auto-detects OpenCode config dir, project root, and Python.
#
# Usage:
#   .\install.ps1
#   .\install.ps1 -Project C:\project
#   .\install.ps1 -Project . -Offline

param(
    [string]$Project = "",
    [switch]$Offline = $false
)

$RepoBase = "https://raw.githubusercontent.com/xxxn3m3s1sxxx/opencode-tools/main"
$ErrorActionPreference = "Stop"
$Tools = @("hashline", "impact", "verify", "trace", "rename", "graph", "changelog", "search", "lint", "refactor", "health", "snapshot", "todo", "tags", "check", "audit", "fmt", "churn", "report", "ghost")
$AllFiles = @("utils.ts") + ($Tools | ForEach-Object {
    $tsfile = if ($_ -eq "trace") { "calltrace" } else { $_ }
    "$tsfile.ts", "$_.py"
})

function Write-Step($msg) { Write-Host "  $msg" -ForegroundColor Green }
function Write-Skip($msg) { Write-Host "  $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "  $msg" -ForegroundColor Red }

# --- Detect OpenCode config dir ---
$OpencodeDir = if (Test-Path "$env:XDG_CONFIG_HOME\opencode") {
    "$env:XDG_CONFIG_HOME\opencode"
} elseif (Test-Path "$env:HOME\.config\opencode") {
    "$env:HOME\.config\opencode"
} elseif (Test-Path "$env:USERPROFILE\.config\opencode") {
    "$env:USERPROFILE\.config\opencode"
} else {
    "$env:USERPROFILE\.config\opencode"
}

# --- Detect project root ---
if (-not $Project) {
    $Project = & git rev-parse --show-toplevel 2>$null
    if (-not $Project) { $Project = (Get-Location).Path }
}
$Project = (Resolve-Path $Project -ErrorAction SilentlyContinue).Path
if (-not $Project) { $Project = (Get-Location).Path }

# --- Detect script source dir ---
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { "" }

Write-Host "`n  +------------------------------------------+"
Write-Host "  |  OpenCode Tools Installer                |"
Write-Host "  |  20 plugins + engines                    |"
Write-Host "  +------------------------------------------+`n"
Write-Host "  Config: $OpencodeDir"
Write-Host "  Project: $Project`n"

# --- Helper ---
function Install-File($src, $dest, $name) {
    if ($ScriptDir -and (Test-Path "$ScriptDir\$src")) {
        Copy-Item -LiteralPath "$ScriptDir\$src" -Destination $dest -Force
        Write-Step "$name -> $dest (local)"
        return $true
    }
    if (-not $Offline) {
        try {
            $url = "$RepoBase/$src" -replace '\\', '/'
            Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -ErrorAction Stop
            Write-Step "$name -> $dest (downloaded)"
            return $true
        } catch {
            Write-Err "Download failed: $_"
        }
    }
    Write-Err "SKIP $src (not found)"
    return $false
}

# --- Install plugins ---
$PluginDir = "$OpencodeDir\plugins"
if (-not (Test-Path $PluginDir)) { New-Item -ItemType Directory -Path $PluginDir -Force | Out-Null }

# utils.ts (shared)
Write-Host "  [utils] plugin..."
Install-File "utils.ts" "$PluginDir\utils.ts" "utils.ts"

foreach ($tool in $Tools) {
    $tsfile = if ($tool -eq "trace") { "calltrace" } else { $tool }
    Write-Host "  [$tool] plugin..."
    Install-File "$tsfile.ts" "$PluginDir\$tsfile.ts" "$tsfile.ts"
}

# --- Install to .opencode/plugins (project-local, auto-discovered) ---
$LocalPluginDir = "$Project\.opencode\plugins"
if (-not (Test-Path $LocalPluginDir)) { New-Item -ItemType Directory -Path $LocalPluginDir -Force | Out-Null }
Install-File "utils.ts" "$LocalPluginDir\utils.ts" "utils.ts (.opencode)"
foreach ($tool in $Tools) {
    $tsfile = if ($tool -eq "trace") { "calltrace" } else { $tool }
    $LocalTs = "$LocalPluginDir\$tsfile.ts"
    if (-not (Test-Path $LocalTs)) {
        Install-File "$tsfile.ts" "$LocalTs" "$tsfile.ts (.opencode)"
    }
}

# --- Install .py to plugin dir ---
foreach ($tool in $Tools) {
    $pyfile = if ($tool -eq "trace") { "calltrace" } else { $tool }
    $PluginPy = "$PluginDir\$pyfile.py"
    if (-not (Test-Path $PluginPy)) {
        Install-File "$pyfile.py" "$PluginPy" "$pyfile.py (plugin)"
    }
}

# --- Install engines (project root) ---
foreach ($tool in $Tools) {
    $pyfile = if ($tool -eq "trace") { "calltrace" } else { $tool }
    $EngineDest = "$Project\$pyfile.py"
    if (Test-Path $EngineDest) {
        Write-Skip "  [$tool] engine -> $EngineDest (exists)"
    } else {
        Write-Host "  [$tool] engine (as $pyfile.py)..."
        Install-File "$pyfile.py" "$EngineDest" "$pyfile.py"
        if (-not (Test-Path $EngineDest)) {
            Write-Err "  [$tool] engine INSTALL FAILED"
        }
    }
}

# --- Verify ---
Write-Host ""
foreach ($tool in $Tools) {
    $pyfile = if ($tool -eq "trace") { "calltrace" } else { $tool }
    $Engine = "$Project\$pyfile.py"
    if (Test-Path $Engine) {
        try {
            $v = (& python $Engine --version 2>&1) -join ' '
            if ($LASTEXITCODE -eq 0) { Write-Step "$($tool): $v" }
            else { Write-Skip "$($tool): verify failed" }
        } catch { Write-Skip "$($tool): python not found" }
    }
}

# --- Done ---
Write-Host "`n  Tools installed! Restart OpenCode to activate.`n"
if (Test-Path "$PSScriptRoot\pyproject.toml") {
    Write-Host "  Optional: pip install -e `"$PSScriptRoot`""
    Write-Host "  (makes graph, lint, impact, ... available system-wide)`n"
}
Write-Host "  Installed: $($Tools -join ', ')`n"
Write-Host "  Test:"
foreach ($tool in $Tools) {
    $pyfile = if ($tool -eq "trace") { "calltrace" } else { $tool }
    Write-Host "    python $Project\$pyfile.py --version"
}
Write-Host ""
