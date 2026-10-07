param(
    [switch]$ForceInstall
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$pipExe = Join-Path $root ".venv\Scripts\pip.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "Creating virtual environment..."
    python -m venv (Join-Path $root ".venv")
}

if ($ForceInstall -or -not (Test-Path $pipExe)) {
    throw "pip was not found in .venv. Recreate the environment."
}

Write-Host "Installing dependencies..."
& $pythonExe -m pip install -r (Join-Path $root "requirements.txt")

Write-Host "Environment ready: $pythonExe"
