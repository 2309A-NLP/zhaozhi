$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

Write-Host "Starting FastAPI backend and HTML frontend on http://127.0.0.1:8000"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$root'; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)
