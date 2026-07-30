$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compilerCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$compiler = $compilerCandidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if (-not $compiler) { throw "Inno Setup 6 is not installed. Install it explicitly before continuing." }
if (-not (Test-Path -LiteralPath (Join-Path $repo "dist\LockIn\LockIn.exe"))) {
    throw "Build the PyInstaller onedir application before the installer."
}
New-Item -ItemType Directory -Path (Join-Path $repo "release") -Force | Out-Null
& $compiler (Join-Path $repo "installer\LockIn.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }
$output = Join-Path $repo "release\LockIn-Setup-v1.1.1.exe"
if (-not (Test-Path -LiteralPath $output)) { throw "Installer artifact is missing: $output" }
Write-Output "Installer build complete: $output"
