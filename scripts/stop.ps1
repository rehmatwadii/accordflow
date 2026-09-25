$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot 'data/server.pid'
if (Test-Path -LiteralPath $pidFile) {
    $serverPid = [int](Get-Content -LiteralPath $pidFile)
    $serverInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $serverPid"
    if ($serverInfo -and $serverInfo.CommandLine -like '*uvicorn backend.app.main:app*' -and $serverInfo.ExecutablePath -like "$projectRoot*") {
        # Windows venv Python may launch the base interpreter as a child.
        $serverChildren = Get-CimInstance Win32_Process -Filter "ParentProcessId = $serverPid"
        foreach ($child in $serverChildren) {
            if ($child.CommandLine -like '*uvicorn backend.app.main:app*') {
                Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            }
        }
        Stop-Process -Id $serverPid -ErrorAction SilentlyContinue
        Write-Output 'Local AccordFlow server stopped.'
    } else { Write-Output 'Saved process is no longer the local AccordFlow server; no process stopped.' }
}
