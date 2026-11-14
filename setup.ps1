param(
    [string]$PythonExecutable = "",
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Executable $($Arguments -join ' ')"
    }
}

Push-Location -LiteralPath $PSScriptRoot
try {
    if ($env:OS -ne "Windows_NT") {
        throw "This setup targets Windows x64 and Python 3.11. See README for other environments."
    }
    if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
        if ($PythonExecutable) {
            $launcher = $PythonExecutable
            $prefix = @()
        } elseif (Get-Command py -ErrorAction SilentlyContinue) {
            $launcher = "py"
            $prefix = @("-3.11")
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            $launcher = "python"
            $prefix = @()
        } else {
            throw "Install Python 3.11 x64 from python.org, reopen PowerShell, and rerun setup."
        }
        Invoke-Checked -Executable $launcher -Arguments ($prefix + @("-c", "import sys, platform; assert sys.version_info[:2] == (3, 11) and platform.machine().upper() in ('AMD64', 'X86_64') and sys.maxsize > 2**32, 'Python 3.11 x64 is required'"))
        Invoke-Checked -Executable $launcher -Arguments ($prefix + @("-m", "venv", ".venv"))
    }
    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    Invoke-Checked -Executable $python -Arguments @("-c", "import sys, platform; assert sys.version_info[:2] == (3, 11) and platform.machine().upper() in ('AMD64', 'X86_64') and sys.maxsize > 2**32, 'Existing .venv must use Python 3.11 x64; use a fresh clone/environment'")
    Invoke-Checked -Executable $python -Arguments @("-m", "pip", "--disable-pip-version-check", "--use-feature=truststore", "install", "-r", "requirements.txt", "-r", "web-requirements.txt", "-c", "requirements-windows-py311.lock.txt")
    Invoke-Checked -Executable $python -Arguments @("-m", "pip", "check")

    if (-not $SkipModels) {
        Write-Host "Provisioning local English recognition (first run needs internet)..."
        Invoke-Checked -Executable $python -Arguments @("-c", "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')")
        $ollamaUrl = "http://127.0.0.1:11434"
        if ($env:PRIYA_OLLAMA_URL) { $ollamaUrl = $env:PRIYA_OLLAMA_URL.TrimEnd("/") }
        $model = "qwen2.5:1.5b"
        if ($env:PRIYA_OLLAMA_MODEL) { $model = $env:PRIYA_OLLAMA_MODEL }
        try {
            $tags = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 10
        } catch {
            throw "Ollama is not reachable. Install/start Ollama from https://ollama.com/download/windows, reopen PowerShell, and rerun setup. If using a trusted remote service, set PRIYA_OLLAMA_URL."
        }
        if (@($tags.models | ForEach-Object { $_.name }) -notcontains $model) {
            Write-Host "Downloading Ollama model $model (this can take several minutes)..."
            $result = Invoke-RestMethod -Uri "$ollamaUrl/api/pull" -Method Post -ContentType "application/json" -Body (@{ model = $model; stream = $false } | ConvertTo-Json) -TimeoutSec 1800
            if ($result.PSObject.Properties["error"]) { throw "Ollama model provisioning failed: $($result.error)" }
            $tags = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 10
            if (@($tags.models | ForEach-Object { $_.name }) -notcontains $model) {
                throw "Ollama did not confirm the requested model. Check its service and rerun setup."
            }
        }
        Write-Host "Ollama model is available: $model"
    } else {
        Write-Warning "Model provisioning was skipped. This is not a full voice/AI setup; rerun without -SkipModels before using those features."
    }

    Invoke-Checked -Executable $python -Arguments @("-m", "app_monitor", "--test")
    Write-Host "Dependencies and regression checks passed."
    Write-Host "Start Priya with: powershell -NoProfile -File .\start.ps1"
    Write-Host "For a new-laptop task restore, follow docs\NEW_LAPTOP_WINDOWS.md before first starting the app."
} finally {
    Pop-Location
}
