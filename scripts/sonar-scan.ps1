# Run SonarScanner CLI in Docker against the local SonarQube instance.
# Requires SONAR_TOKEN (and optionally SONAR_HOST_URL) in .env or the environment.
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $Root ".env"

if (-not $env:SONAR_TOKEN -and (Test-Path $envFile)) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*SONAR_TOKEN=(.+)$') {
            $env:SONAR_TOKEN = $matches[1].Trim().Trim('"').Trim("'")
        }
        if ($_ -match '^\s*SONAR_HOST_URL=(.+)$') {
            $env:SONAR_HOST_URL = $matches[1].Trim().Trim('"').Trim("'")
        }
    }
}

if (-not $env:SONAR_TOKEN) {
    throw "SONAR_TOKEN is not set. Add it to .env (see .env.example) or export it for this session."
}

# Scanner runs in Docker; localhost in .env is for the browser, not the scanner container.
$scannerHostUrl = if ($env:SONAR_SCANNER_HOST_URL) {
    $env:SONAR_SCANNER_HOST_URL
} elseif ($env:SONAR_HOST_URL -and $env:SONAR_HOST_URL -notmatch 'localhost|127\.0\.0\.1') {
    $env:SONAR_HOST_URL
} else {
    "http://host.docker.internal:9000"
}
$env:SONAR_HOST_URL = $scannerHostUrl

if ($env:SONAR_SKIP_COVERAGE -ne "1") {
    Write-Host "Generating coverage.xml via pytest-cov"
    & uv run pytest --cov=app --cov-report=xml -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed; aborting scan" }
}

Write-Host "Scanning $Root -> $scannerHostUrl"

docker run --rm `
    -e SONAR_HOST_URL=$scannerHostUrl `
    -e SONAR_TOKEN=$env:SONAR_TOKEN `
    -v "${Root}:/usr/src" `
    -w /usr/src `
    sonarsource/sonar-scanner-cli
