# MuskTracker Setup Script
# Run this script to set up the project from scratch

Write-Host "=== MuskTracker Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($pythonVersion -match "Python 3\.1[1-9]") {
    Write-Host "✓ Python version OK: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "Virtual environment already exists. Skipping." -ForegroundColor Gray
} else {
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1
Write-Host "✓ Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "✓ pip upgraded" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes..." -ForegroundColor Gray
pip install -r requirements.txt --quiet
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Check .env file
Write-Host ""
Write-Host "Checking configuration..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "✓ .env file found" -ForegroundColor Green
} else {
    Write-Host "✗ .env file not found. Creating from template..." -ForegroundColor Red
    Copy-Item ".env.example" ".env"
    Write-Host "⚠ Please edit .env with your X API credentials" -ForegroundColor Yellow
    exit 0
}

# Initialize database
Write-Host ""
Write-Host "Initializing database..." -ForegroundColor Yellow
python -m musktracker.cli.migrate up
Write-Host "✓ Database initialized" -ForegroundColor Green

# Ingest initial data
Write-Host ""
Write-Host "Ingesting initial data (last 7 days)..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes due to API rate limits..." -ForegroundColor Gray
python -m musktracker.cli.ingest --backfill-days 7
Write-Host "✓ Initial data ingested" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Train models: python -m musktracker.cli.train --model all" -ForegroundColor White
Write-Host "  2. Generate forecast: python -m musktracker.cli.forecast --horizon 24h" -ForegroundColor White
Write-Host ""
Write-Host "See QUICKSTART.md for more details." -ForegroundColor Gray

