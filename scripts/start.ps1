$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
}
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
& $pythonPath -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $pythonPath -m scripts.configure
& $pythonPath -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& $pythonPath -m scripts.seed
if ($LASTEXITCODE -ne 0) { throw 'Seed failed' }
Push-Location -LiteralPath 'frontend'
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) { Write-Output 'Port 8000 already in use. Existing app may be at http://127.0.0.1:8000'; exit }
$serverProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8000','--no-access-log' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'data/server.log' -RedirectStandardError 'data/server-error.log'
$serverProcess.Id | Set-Content -LiteralPath 'data/server.pid'
$serviceReady = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health/ready' -TimeoutSec 2
        if ($health.status -eq 'READY') { $serviceReady = $true; break }
    } catch { Start-Sleep -Milliseconds 300 }
}
if (-not $serviceReady) { throw 'Server did not become ready. Inspect data/server-error.log.' }
Write-Output 'LC-Verify: http://127.0.0.1:8000'
Write-Output 'API docs: http://127.0.0.1:8000/api/docs'
Write-Output 'Demo password: .demo-credentials.json (local file only)'
