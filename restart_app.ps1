param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectDirectory = $PSScriptRoot
$workspaceDirectory = (Resolve-Path (Join-Path $projectDirectory "..\..")).Path
$pythonExecutable = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonSitePackages = Join-Path (Split-Path $pythonExecutable -Parent) "Lib\site-packages"
$workDirectory = Join-Path $workspaceDirectory "work"
$logDirectory = Join-Path $workDirectory "streamlit_logs"
$pidFile = Join-Path $logDirectory "server.pid"
$stdoutLog = Join-Path $logDirectory "server.stdout.log"
$stderrLog = Join-Path $logDirectory "server.stderr.log"
$healthUrl = "http://127.0.0.1:8501/_stcore/health"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw "Python runtime not found: $pythonExecutable"
}

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $trackedPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($trackedPid) {
        $trackedProcess = Get-Process -Id $trackedPid -ErrorAction SilentlyContinue
        if ($trackedProcess) {
            Stop-Process -Id $trackedPid -Force
            Wait-Process -Id $trackedPid -Timeout 10 -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

# Освобождаем порт после аварийного завершения, если PID-файл не сохранился.
$listener = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    $listenerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction SilentlyContinue
    if ($listenerProcess -and $listenerProcess.CommandLine -match "streamlit\s+run\s+app\.py") {
        Stop-Process -Id $listener.OwningProcess -Force
        Wait-Process -Id $listener.OwningProcess -Timeout 10 -ErrorAction SilentlyContinue
    } else {
        throw "Port 8501 is occupied by another application."
    }
}

$env:PYTHONPATH = @(
    $pythonSitePackages
    (Join-Path $workDirectory "python-app-deps")
    (Join-Path $workDirectory "python-test-deps")
) -join ";"
$env:PYTHONIOENCODING = "utf-8"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"

$arguments = @(
    "-m", "streamlit", "run", "app.py",
    "--global.developmentMode=false",
    "--server.headless=true",
    "--browser.gatherUsageStats=false",
    "--server.address=127.0.0.1",
    "--server.port=8501"
)

$server = Start-Process `
    -FilePath $pythonExecutable `
    -ArgumentList $arguments `
    -WorkingDirectory $projectDirectory `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$server.Id | Out-File -FilePath $pidFile -Encoding ascii

for ($attempt = 1; $attempt -le 60; $attempt++) {
    Start-Sleep -Milliseconds 250
    if ($server.HasExited) {
        $errorTail = Get-Content -LiteralPath $stderrLog -Tail 20 -ErrorAction SilentlyContinue
        throw "Streamlit stopped during startup.`n$errorTail"
    }
    try {
        $health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
        if ($health.StatusCode -eq 200 -and $health.Content.Trim() -eq "ok") {
            if (-not $NoBrowser) {
                Start-Process "http://127.0.0.1:8501/"
            }
            Write-Host "Application restarted: http://127.0.0.1:8501/"
            exit 0
        }
    } catch {
        # Сервер ещё запускается.
    }
}

throw "Streamlit did not start. Check log: $stderrLog"
