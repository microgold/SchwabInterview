param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "dev-interview-key"
)

$ErrorActionPreference = "Stop"

$headers = @{
    "X-API-Key" = $ApiKey
    "Content-Type" = "application/json"
}

Write-Host "Checking health endpoint..."
$health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get
if ($health.status -ne "ok") {
    throw "Health check failed."
}

Write-Host "Creating short URL..."
$payload = @{ url = "https://example.com/smoke" } | ConvertTo-Json
$created = Invoke-RestMethod -Uri "$BaseUrl/api/v1/shorten" -Method Post -Headers $headers -Body $payload
if (-not $created.short_code) {
    throw "Shorten API did not return short_code."
}
$code = $created.short_code
Write-Host "Created code: $code"

Write-Host "Retrieving URL metadata..."
$urlInfo = Invoke-RestMethod -Uri "$BaseUrl/api/v1/urls/$code" -Method Get -Headers @{ "X-API-Key" = $ApiKey }
if ($urlInfo.short_code -ne $code) {
    throw "URL metadata did not match short code."
}

Write-Host "Hitting redirect endpoint..."
$redirectHandler = [System.Net.Http.HttpClientHandler]::new()
$redirectHandler.AllowAutoRedirect = $false
$redirectClient = [System.Net.Http.HttpClient]::new($redirectHandler)
try {
    $redirectResponse = $redirectClient.GetAsync("$BaseUrl/$code").GetAwaiter().GetResult()
    $redirectStatus = [int]$redirectResponse.StatusCode
}
finally {
    if ($null -ne $redirectResponse) {
        $redirectResponse.Dispose()
    }
    $redirectClient.Dispose()
    $redirectHandler.Dispose()
}
if ($redirectStatus -ne 307) {
    throw "Expected 307 redirect status, got $redirectStatus"
}

Write-Host "Retrieving analytics..."
$analytics = Invoke-RestMethod -Uri "$BaseUrl/api/v1/analytics/$code" -Method Get -Headers @{ "X-API-Key" = $ApiKey }
if ($analytics.total_clicks -lt 1) {
    throw "Expected at least 1 click in analytics."
}

Write-Host "Smoke test passed ✅"
