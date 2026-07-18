$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$exe = Join-Path $repo "dist\LockIn\LockIn.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "Packaged executable is missing: $exe" }
$token = [guid]::NewGuid().ToString("N")
$root = Join-Path $env:TEMP "lockin-packaged-smoke-$token"
$env:LOCKIN_RUNTIME_ROOT = Join-Path $root "runtime space Ω"
$env:LOCKIN_PORTABLE_ROOT = Join-Path $root "portable space Ω"
$env:LOCKIN_SETTINGS_PATH = Join-Path $root "settings.ini"
$health = Join-Path $root "health.json"
New-Item -ItemType Directory -Path $root -Force | Out-Null

$process = Start-Process -FilePath $exe `
    -ArgumentList @("--health-check-output", "`"$health`"") `
    -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -ne 0) {
    throw "Packaged health check failed with exit code $($process.ExitCode)"
}
$report = Get-Content -Raw -LiteralPath $health | ConvertFrom-Json
if ($report.result -ne "ok" -or $report.version -ne "1.0.0" -or -not $report.frozen) {
    throw "Packaged health JSON did not report a healthy frozen 1.0.0 build."
}
if (-not (Test-Path -LiteralPath (Join-Path $env:LOCKIN_RUNTIME_ROOT "lockin.sqlite3"))) {
    throw "Packaged health check did not initialize the isolated SQLite database."
}
$forbidden = Get-ChildItem -LiteralPath (Join-Path $repo "dist\LockIn") -Recurse -File |
    Where-Object { $_.Name -match '\.(db|sqlite|sqlite3|log|bak)$' -or $_.Name -match '\.(db-wal|db-shm)$' }
if ($forbidden) { throw "Packaged bundle contains runtime data: $($forbidden.FullName -join ', ')" }
Write-Output "Packaged smoke test: OK"
Write-Output "health=$health"
Write-Output "runtime=$env:LOCKIN_RUNTIME_ROOT"
Write-Output "portable=$env:LOCKIN_PORTABLE_ROOT"
