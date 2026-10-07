param(
    [int]$Port = 8000,
    [string]$ApiKey = "dev-interview-key",
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$apiProcess = $null

function Invoke-Checked {
    param(
        [scriptblock]$Command,
        [string]$ErrorMessage
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

function Wait-ForApi {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 20
    )

    $start = Get-Date
    while (((Get-Date) - $start).TotalSeconds -lt $TimeoutSeconds) {
        try {
            $response = Invoke-RestMethod -Uri "$Url/health" -Method Get -TimeoutSec 2
            if ($response.status -eq "ok") {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "API did not become healthy within $TimeoutSeconds seconds."
}

try {
    if (-not $SkipInstall) {
        & (Join-Path $root "scripts\setup_env.ps1")
        if ($LASTEXITCODE -ne 0) {
            throw "Environment setup failed."
        }
    }

    Write-Host "Running pytest..."
    Invoke-Checked -Command { & $pythonExe -m pytest -q } -ErrorMessage "pytest failed."

    Write-Host "Running workflow demo..."
    Invoke-Checked -Command { & $pythonExe (Join-Path $root "scripts\run_workflow_demo.py") } -ErrorMessage "Workflow demo failed."

    $env:SHORTENER_API_KEY = $ApiKey
    Write-Host "Starting API in background on port $Port..."
    $apiProcess = Start-Process -FilePath $pythonExe `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--port", "$Port") `
        -WorkingDirectory $root `
        -PassThru

    Wait-ForApi -Url "http://127.0.0.1:$Port"

    Write-Host "Running API smoke test..."
    & (Join-Path $root "scripts\smoke_test.ps1") -BaseUrl "http://127.0.0.1:$Port" -ApiKey $ApiKey
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke test failed."
    }

    Write-Host "`nAll verification checks passed ✅"
    Write-Host "UI: http://127.0.0.1:$Port/ui"
}
finally {
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id
        Write-Host "Stopped background API process (PID: $($apiProcess.Id))."
    }
}
