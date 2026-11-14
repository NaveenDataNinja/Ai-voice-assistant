param(
    [ValidateRange(1, 65535)]
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Run setup.ps1 first to create this clone's environment."
}
Push-Location -LiteralPath $PSScriptRoot
try {
    $env:PORT = [string]$Port
    Write-Host "Opening the local server at http://127.0.0.1:$Port (Ctrl+C to stop)."
    & $python web_app.py
    if ($LASTEXITCODE -ne 0) { throw "Priya exited with code $LASTEXITCODE. Check the error above." }
} finally {
    Pop-Location
}
