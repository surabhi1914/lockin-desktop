$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Remove-GeneratedDirectory([string]$RelativePath) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $repo $RelativePath))
    $prefix = $repo.TrimEnd('\') + '\'
    if (-not $target.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove a path outside the repository: $target"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}

Remove-GeneratedDirectory "build"
Remove-GeneratedDirectory "dist"
Remove-GeneratedDirectory "release"
Remove-GeneratedDirectory "installer-output"
Write-Output "Generated build directories removed safely."
