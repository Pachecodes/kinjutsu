[CmdletBinding()]
param([string]$InstallRoot, [switch]$PackageOnly)
. (Join-Path $PSScriptRoot 'Common-Kinjutsu.ps1')
$root = Resolve-KinjutsuRoot $InstallRoot
if ($PackageOnly) {
    # Package verification never installs anything, starts services, or imports torch.
    $python = Join-Path $root 'runtime/venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $found = Get-Command python -ErrorAction SilentlyContinue
        if (-not $found) { throw 'Offline package verification needs a Python 3.12+ interpreter on PATH, or the installed runtime.' }
        $python = $found.Source
    }
    & $python -s (Join-Path $root 'scripts/kinjutsu.py') verify-package --root $root
    if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }
} else { Invoke-Kinjutsu $root 'verify' }
