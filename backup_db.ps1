$ErrorActionPreference = "Stop"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dbPath = "data\football.db"
$backupDir = "data\backups"
$backupFile = "$backupDir\football_$timestamp.db"

if (-not (Test-Path $dbPath)) {
    Write-Host "No database found at $dbPath" -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
}

Copy-Item -Path $dbPath -Destination $backupFile -Force
Write-Host "Database backed up successfully to $backupFile" -ForegroundColor Green
