#Requires -Version 5.1
<#
.SYNOPSIS
    Build wisclaw.exe for Windows using PyInstaller.

.DESCRIPTION
    Creates a Python virtual environment, installs dependencies, and runs
    PyInstaller to produce a standalone wisclaw.exe binary.

.EXAMPLE
    .\scripts\build-wisclaw.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BridgeDir = Join-Path $RepoRoot "bridge"
$VenvDir = Join-Path $RepoRoot ".venv-build"
$SpecFile = Join-Path $BridgeDir "wisclaw.spec"

# Detect architecture for output naming
$Arch = switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture) {
    "X64"   { "x64" }
    "X86"   { "x86" }
    "Arm64" { "arm64" }
    default { "unknown" }
}

# ── Helpers ───────────────────────────────────────────────────────────────

function Assert-Command {
    param([string]$Name, [string]$HelpUrl)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: '$Name' not found in PATH." -ForegroundColor Red
        if ($HelpUrl) {
            Write-Host "Install it from: $HelpUrl"
        }
        exit 1
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ">>> $Message" -ForegroundColor Cyan
}

# ── Preflight checks ─────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== wisclaw Windows builder ===" -ForegroundColor Cyan
Write-Host ""

Assert-Command -Name "python" -HelpUrl "https://www.python.org/downloads/"
Assert-Command -Name "pip" -HelpUrl "https://pip.pypa.io/en/stable/installation/"

$pyVersion = python --version 2>&1
Write-Host "Python:       $pyVersion"
Write-Host "Architecture: $Arch"
Write-Host "Repo root:    $RepoRoot"

# ── Virtual environment ──────────────────────────────────────────────────

Write-Step "Creating virtual environment at $VenvDir"

if (Test-Path $VenvDir) {
    Write-Host "Reusing existing venv."
} else {
    python -m venv $VenvDir
}

$ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
    Write-Host "ERROR: venv activation script not found at $ActivateScript" -ForegroundColor Red
    exit 1
}

& $ActivateScript

# ── Install dependencies ─────────────────────────────────────────────────

Write-Step "Installing dependencies"

$RequirementsFile = Join-Path $BridgeDir "requirements.txt"
if (Test-Path $RequirementsFile) {
    pip install --quiet -r $RequirementsFile
}

pip install --quiet pyinstaller certifi

# ── Build ────────────────────────────────────────────────────────────────

Write-Step "Running PyInstaller"

if (-not (Test-Path $SpecFile)) {
    Write-Host "ERROR: Spec file not found at $SpecFile" -ForegroundColor Red
    Write-Host "Ensure bridge/wisclaw.spec exists in the repo root."
    exit 1
}

Push-Location $RepoRoot
try {
    pyinstaller --clean --noconfirm $SpecFile
} finally {
    Pop-Location
}

# ── Rename output with architecture tag ──────────────────────────────────

$RawExe = Join-Path $RepoRoot "dist\wisclaw.exe"
$TaggedName = "wisclaw-windows-$Arch.exe"
$TaggedExe = Join-Path $RepoRoot "dist\$TaggedName"

if (Test-Path $RawExe) {
    Copy-Item $RawExe $TaggedExe -Force
    $size = (Get-Item $TaggedExe).Length / 1MB
    Write-Host ""
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "  Output: $TaggedExe"
    Write-Host ("  Size:   {0:N1} MB" -f $size)
    Write-Host ""
    Write-Host "Quick verification:"
    Write-Host "  .\dist\$TaggedName version"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "ERROR: Expected output not found at $RawExe" -ForegroundColor Red
    Write-Host "Check the PyInstaller output above for errors."
    exit 1
}
