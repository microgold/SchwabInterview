param(
    [int]$Port = 8000,
    [string]$ApiKey = "dev-interview-key"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Virtual environment not found. Run .\scripts\setup_env.ps1 first."
}

$env:SHORTENER_API_KEY = $ApiKey

Write-Host "Starting API on http://localhost:$Port (UI: /ui)"
& $pythonExe -m uvicorn app.main:app --reload --port $Port
