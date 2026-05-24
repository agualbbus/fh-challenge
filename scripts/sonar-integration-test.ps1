# End-to-end check: SonarQube up, healthy, and scanner upload succeeds.
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

function Wait-SonarHealthy {
    param([int]$TimeoutSeconds = 180)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    Write-Host "Waiting for SonarQube at http://localhost:9000 ..."
    while ((Get-Date) -lt $deadline) {
        try {
            $status = Invoke-RestMethod -Uri "http://localhost:9000/api/system/status" -TimeoutSec 5
            if ($status.status -eq "UP") {
                Write-Host "SonarQube is UP."
                return
            }
        } catch {
            # still starting
        }
        Start-Sleep -Seconds 5
    }
    throw "SonarQube did not become healthy within ${TimeoutSeconds}s."
}

Write-Host "==> Starting SonarQube (persistent data: docker/sonarqube/)"
docker compose -f docker-compose.sonar.yml up -d

Wait-SonarHealthy

Write-Host "==> Running scanner"
& (Join-Path $PSScriptRoot "sonar-scan.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Integration test passed."
Write-Host "Dashboard: http://localhost:9000/dashboard?id=fh"
