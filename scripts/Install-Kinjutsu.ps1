[CmdletBinding()]
param([string]$InstallRoot, [switch]$DryRun, [switch]$AcceptLicenses)
. (Join-Path $PSScriptRoot 'Common-Kinjutsu.ps1')
$root = Resolve-KinjutsuRoot $InstallRoot
if ($DryRun) {
    # Offline; does not bootstrap tools, create files, or resolve network packages.
    $manifest = Get-Content -LiteralPath (Join-Path $root 'models/manifest.json') -Raw | ConvertFrom-Json
    $defaultModels = @($manifest.models | Where-Object { -not ($_.PSObject.Properties.Name -contains 'optional') -or -not $_.optional })
    [ordered]@{Title='Pachecodes : Kinjutsu';Root=$root;Python='3.12.10';CoreRevision='7a131a3afadc8200120f67f9236311a2c48b7445';Comfy='127.0.0.1:8218';Studio='127.0.0.1:8220';Models=$defaultModels;Lock='dependencies/requirements.lock';AutoStart=$false;Actions='Verify package; bootstrap portable uv/git + FFmpeg/ffprobe pair; isolated venv; pinned hash dependencies; exact core + backports; verified weights; prebuilt sanitized frontend; verify only, no services'} | ConvertTo-Json -Depth 8
    exit 0
}
if (-not $AcceptLicenses) {
    Add-Type -AssemblyName System.Windows.Forms
    $answer = [System.Windows.Forms.MessageBox]::Show('Lea licenses/ y THIRD_PARTY_NOTICES.md. Descarga de modelos base: 42.470.585.471 bytes mas herramientas y dependencias. Uso local; BFS restringe reventa/servicios alojados. Acepta licencias y descargas?', 'Kinjutsu - consentimiento', 'YesNo', 'Information')
    if ($answer -ne 'Yes') { throw 'Instalacion cancelada antes de descargar.' }
}
if (-not (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue)) { throw 'Instale controlador NVIDIA compatible con CUDA 13 antes de continuar.' }
Set-KinjutsuEnvironment $root
Initialize-KinjutsuTools $root
$uv = Join-Path $root 'runtime/tools/uv/uv.exe'
$python = Join-Path $root 'runtime/venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (Test-Path -LiteralPath (Join-Path $root 'runtime/venv')) { throw 'Incomplete runtime/venv exists; inspect manually. Installer never resets it.' }
    & $uv venv --managed-python --python 3.12.10 (Join-Path $root 'runtime/venv')
    if ($LASTEXITCODE -ne 0) { throw 'Isolated Python bootstrap failed.' }
}
Invoke-Kinjutsu $root 'install'
