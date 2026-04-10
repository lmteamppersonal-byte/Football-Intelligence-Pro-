$ErrorActionPreference = "Stop"

$backupDir = "data\backups"
$dbPath = "data\football.db"

if (-not (Test-Path $backupDir)) {
    Write-Host "No backup directory found at $backupDir" -ForegroundColor Red
    exit 1
}

$latestBackup = Get-ChildItem -Path $backupDir -Filter "football_*.db" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $latestBackup) {
    Write-Host "No backup files found in $backupDir" -ForegroundColor Red
    exit 1
}

Write-Host "Found latest backup: $($latestBackup.Name)" -ForegroundColor Cyan
$confirmation = Read-Host "Are you sure you want to restore this backup? This will overwrite your current database. (y/n)"

if ($confirmation -eq 'y') {
    Copy-Item -Path $latestBackup.FullName -Destination $dbPath -Force
    Write-Host "Database restored successfully from $($latestBackup.Name)" -ForegroundColor Green
} else {
    Write-Host "Restore operation cancelled." -ForegroundColor Yellow
}
