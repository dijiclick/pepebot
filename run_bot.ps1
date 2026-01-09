# PEPE Scalping Bot - Auto-restart script for Windows
# Run this script to start the bot with auto-restart on crash

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PEPE Scalping Bot - Auto-restart Mode" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
Set-Location $PSScriptRoot

# Activate virtual environment if exists
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
    . .\venv\Scripts\Activate.ps1
}

while ($true) {
    Write-Host ""
    Write-Host "[*] Starting bot..." -ForegroundColor Green
    Write-Host "[*] Press Ctrl+C to stop" -ForegroundColor Gray
    Write-Host ""

    # Run the bot
    python src/main.py

    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "[*] Bot stopped gracefully." -ForegroundColor Yellow
        break
    }

    Write-Host ""
    Write-Host "[!] Bot crashed with exit code: $exitCode" -ForegroundColor Red
    Write-Host "[*] Restarting in 5 seconds..." -ForegroundColor Yellow
    Write-Host "[*] Press Ctrl+C to cancel restart" -ForegroundColor Gray

    Start-Sleep -Seconds 5
}

Write-Host ""
Write-Host "[*] Script ended." -ForegroundColor Cyan
