[CmdletBinding()]
param([string]$InstallRoot,[switch]$Offline)
. (Join-Path $PSScriptRoot 'Common-Kinjutsu.ps1')
$root = Resolve-KinjutsuRoot $InstallRoot
Set-KinjutsuEnvironment $root
$uv = Join-Path $root 'runtime/tools/uv/uv.exe'
$python = Join-Path $root 'runtime/venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $uv) -or -not (Test-Path -LiteralPath $python)) { throw 'Initialize the isolated tools/environment with Install-Kinjutsu.ps1 first; dependency check will not bootstrap.' }
$extra = @()
if ($Offline) { $extra += '--offline' }
& $uv pip install --python $python --dry-run --no-deps --require-hashes --only-binary ':all:' --index 'https://download.pytorch.org/whl/cu130' --index-strategy unsafe-best-match -r (Join-Path $root 'dependencies/requirements.lock') @extra
if ($LASTEXITCODE -ne 0) { throw 'Dependency dry-run failed. Offline mode needs cached metadata; no runtime is modified.' }
