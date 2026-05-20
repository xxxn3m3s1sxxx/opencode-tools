# OpenCode Tools — Combined installer (PowerShell)
#
# Installs all OpenCode tools (13 plugins + engines) in one command.
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
$Tools = @("hashline", "impact", "verify", "trace", "rename", "graph", "changelog", "search", "lint", "refactor")
$AllFiles = @("utils.ts") + ($Tools | ForEach-Object { "$_.ts", "$_.py" })

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
Write-Host "  |  13 plugins + engines                    |"
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
    Write-Host "  [$tool] plugin..."
    Install-File "$tool.ts" "$PluginDir\$tool.ts" "$tool.ts"
}

# --- Install engines ---
foreach ($tool in $Tools) {
    $EngineDest = "$Project\$tool.py"
    if (Test-Path $EngineDest) {
        Write-Skip "  [$tool] engine -> $EngineDest (exists)"
    } else {
        Write-Host "  [$tool] engine..."
        Install-File "$tool.py" "$EngineDest" "$tool.py"
        if (-not (Test-Path $EngineDest)) {
            Write-Err "  [$tool] engine INSTALL FAILED"
        }
    }
}

# --- Verify ---
Write-Host ""
foreach ($tool in $Tools) {
    $Engine = "$Project\$tool.py"
    if (Test-Path $Engine) {
        try {
            $v = & python $Engine --version 2>&1
            if ($LASTEXITCODE -eq 0) { Write-Step "$tool: $v" }
            else { Write-Skip "$tool: verify failed" }
        } catch { Write-Skip "$tool: python not found" }
    }
}

# --- Done ---
Write-Host "`n  Tools installed! Restart OpenCode to activate.`n"
Write-Host "  Installed: $($Tools -join ', ')`n"
Write-Host "  Test:"
foreach ($tool in $Tools) {
    Write-Host "    python $Project\$tool.py --version"
}
Write-Host ""
