[CmdletBinding()]
param(
    [string]$ServerScript,
    [string]$UiScript
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot

function Find-EntryPoint {
    param(
        [string]$ExplicitPath,
        [string[]]$Candidates,
        [string]$Description
    )

    if ($ExplicitPath) {
        $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($ExplicitPath)
        if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            throw "$Description script was not found: $resolved"
        }
        return $resolved
    }

    foreach ($candidate in $Candidates) {
        $path = Join-Path $repoRoot $candidate
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            return $path
        }
    }

    $candidateNames = $Candidates | ForEach-Object { Split-Path $_ -Leaf } | Select-Object -Unique
    $matches = Get-ChildItem -LiteralPath $repoRoot -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in $candidateNames -and
            $_.FullName -notmatch '[\\/](\.venv|venv|node_modules|bin|obj|__pycache__)[\\/]'
        }

    if ($matches.Count -eq 1) {
        return $matches[0].FullName
    }

    if ($matches.Count -gt 1) {
        $choices = ($matches.FullName | ForEach-Object { "  $_" }) -join [Environment]::NewLine
        throw "Found multiple possible $Description entry points. Pass the desired path explicitly:$([Environment]::NewLine)$choices"
    }

    throw "Could not find the $Description entry point. Pass it explicitly, for example: .\start.ps1 -ServerScript .\path\server.py -UiScript .\path\simple_ui.py"
}

$venvPython = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    $pythonExecutable = $venvPython
    $pythonPrefix = @()
}
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $pythonExecutable = $python.Source
        $pythonPrefix = @()
    }
    else {
        $python = Get-Command py -ErrorAction SilentlyContinue
        if (-not $python) {
            throw 'Python was not found. Install Python or add py/python to PATH.'
        }
        $pythonExecutable = $python.Source
        $pythonPrefix = @('-3')
    }
}

$serverPath = Find-EntryPoint $ServerScript @(
    'server.py',
    'mcp_server.py',
    'api_server.py',
    'src/server.py',
    'server/server.py',
    'backend/server.py'
) 'server'

$uiPath = Find-EntryPoint $UiScript @(
    'simple_ui.py',
    'simple-ui.py',
    'simpleui.py',
    'ui/simple_ui.py',
    'src/simple_ui.py'
) 'simple UI'

$processes = @()

try {
    Write-Host "Starting server: $serverPath"
    $processes += Start-Process -FilePath $pythonExecutable `
        -ArgumentList ($pythonPrefix + @($serverPath)) `
        -WorkingDirectory (Split-Path -Parent $serverPath) `
        -NoNewWindow -PassThru

    Write-Host "Starting simple UI: $uiPath"
    $processes += Start-Process -FilePath $pythonExecutable `
        -ArgumentList ($pythonPrefix + @($uiPath)) `
        -WorkingDirectory (Split-Path -Parent $uiPath) `
        -NoNewWindow -PassThru

    Write-Host 'Both processes are running. Press Ctrl+C to stop them.'

    while ($true) {
        foreach ($process in $processes) {
            if ($process.HasExited) {
                throw "Process $($process.Id) exited with code $($process.ExitCode)."
            }
        }
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Write-Host 'Stopping server and UI...'
    foreach ($process in $processes) {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
