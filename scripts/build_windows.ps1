$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project .venv Python is missing." }
Set-Location $repo

& $python scripts\generate_app_icon.py
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed." }
& $python scripts\prepare_release_resources.py
if ($LASTEXITCODE -ne 0) { throw "Starter-resource generation failed." }
& $python scripts\validate_release_resources.py
if ($LASTEXITCODE -ne 0) { throw "Starter-resource validation failed." }

$metadata = Join-Path $repo "build\release_metadata"
New-Item -ItemType Directory -Path $metadata -Force | Out-Null
$previousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$commit = (& git rev-parse --verify HEAD 2>$null)
$gitExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorPreference
if ($gitExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($commit)) {
    $commit = "uncommitted-source-tree"
}
$commitPath = Join-Path $metadata "build_commit.txt"
[System.IO.File]::WriteAllText($commitPath, "$commit`n", [System.Text.UTF8Encoding]::new($false))

& $python -m PyInstaller --noconfirm --clean packaging\LockIn.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
if (-not (Test-Path -LiteralPath (Join-Path $repo "dist\LockIn\LockIn.exe"))) {
    throw "PyInstaller did not create dist\LockIn\LockIn.exe"
}
Write-Output "PyInstaller onedir build complete: dist\LockIn\LockIn.exe"
