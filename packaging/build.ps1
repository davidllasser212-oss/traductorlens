$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

.venv\Scripts\python -m PyInstaller --noconfirm --clean packaging\TraductorLens.spec

Write-Host ""
Write-Host "Build completado: $root\dist\TraductorLens.exe" -ForegroundColor Green