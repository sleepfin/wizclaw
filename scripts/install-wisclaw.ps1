#Requires -Version 5.1
<#
.SYNOPSIS
    One-line installer for wisclaw on Windows.

.DESCRIPTION
    Downloads the latest wisclaw.exe from GitHub Releases and installs it
    to %USERPROFILE%\.local\bin, adding that directory to the user PATH
    if it is not already present.

.EXAMPLE
    iwr -useb https://raw.githubusercontent.com/sleepfin/wisclaw/main/scripts/install-wisclaw.ps1 | iex
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Configuration ─────────────────────────────────────────────────────────
$RepoOwner  = "sleepfin"
$RepoName   = "wisclaw"
$BinaryName = "wisclaw.exe"
$InstallDir = Join-Path $env:USERPROFILE ".local\bin"

# ── Helpers ───────────────────────────────────────────────────────────────

function Get-Architecture {
    $arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture
    switch ($arch) {
        "X64"  { return "x64" }
        "Arm64"{ return "arm64" }
        default {
            Write-Host "Unsupported architecture: $arch" -ForegroundColor Red
            exit 1
        }
    }
}

function Get-LatestReleaseUrl {
    param([string]$Arch)

    $apiUrl = "https://api.github.com/repos/$RepoOwner/$RepoName/releases/latest"
    try {
        $release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "wisclaw-installer" }
    }
    catch {
        Write-Host "Failed to query GitHub releases: $_" -ForegroundColor Red
        exit 1
    }

    $pattern = "wisclaw-windows-$Arch"
    $asset = $release.assets | Where-Object { $_.name -like "*$pattern*" } | Select-Object -First 1

    if (-not $asset) {
        Write-Host "No release asset matching '$pattern' found in $($release.tag_name)." -ForegroundColor Red
        Write-Host "Available assets:"
        $release.assets | ForEach-Object { Write-Host "  - $($_.name)" }
        exit 1
    }

    return $asset.browser_download_url
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Write-Host "Created directory: $Path"
    }
}

function Add-ToUserPath {
    param([string]$Dir)

    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    $entries = $currentPath -split ";"

    if ($entries -contains $Dir) {
        Write-Host "$Dir is already in your PATH."
        return
    }

    $newPath = "$currentPath;$Dir"
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    # Also update the current session so the user can use wisclaw immediately
    $env:PATH = "$env:PATH;$Dir"
    Write-Host "Added $Dir to your user PATH."
}

# ── Main ──────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== wisclaw installer ===" -ForegroundColor Cyan
Write-Host ""

$arch = Get-Architecture
Write-Host "Detected architecture: $arch"

$downloadUrl = Get-LatestReleaseUrl -Arch $arch
Write-Host "Downloading from: $downloadUrl"

Ensure-Directory -Path $InstallDir
$destPath = Join-Path $InstallDir $BinaryName

try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $destPath -UseBasicParsing
}
catch {
    Write-Host "Download failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "Installed to: $destPath" -ForegroundColor Green

Add-ToUserPath -Dir $InstallDir

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:"
Write-Host "  wisclaw            # first run will guide you through setup"
Write-Host "  wisclaw config     # re-configure"
Write-Host "  wisclaw version    # show version"
Write-Host ""
Write-Host "You may need to restart your terminal for PATH changes to take effect."
Write-Host ""
