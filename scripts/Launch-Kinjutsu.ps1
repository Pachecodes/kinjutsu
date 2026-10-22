[CmdletBinding()]
param([string]$InstallRoot, [switch]$DryRun)
. (Join-Path $PSScriptRoot 'Common-Kinjutsu.ps1')
$root = Resolve-KinjutsuRoot $InstallRoot
if ($DryRun) { & (Join-Path $PSScriptRoot 'Install-Kinjutsu.ps1') -InstallRoot $root -DryRun; exit $LASTEXITCODE }
$hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))).Replace('-','')
$mutex = [Threading.Mutex]::new($false, ('Local\Kinjutsu_' + $hash))
$hasLock = $false
try { $hasLock = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $hasLock = $true }
if (-not $hasLock) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Ya hay un inicio/instalacion activo para esta carpeta. Espere y consulte runtime/logs/launcher.log.', 'Kinjutsu') | Out-Null
    $mutex.Dispose(); exit 1
}
$logDir = Join-Path $root 'runtime/logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'launcher.log'
Start-Transcript -LiteralPath $log -Append | Out-Null
try {
    Write-Host 'Pachecodes : Kinjutsu - comprobando instalacion local...'
    $python = Join-Path $root 'runtime/venv/Scripts/python.exe'
    $receipt = Join-Path $root 'runtime/installed.json'
    $needsInstall = -not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $receipt)
    if (-not $needsInstall) {
        $installed = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json
        $lock = (Get-FileHash -LiteralPath (Join-Path $root 'dependencies/requirements.lock') -Algorithm SHA256).Hash.ToLowerInvariant()
        $needsInstall = $installed.root -ne $root -or $installed.lock_sha256 -ne $lock
    }
    if ($needsInstall) {
        Add-Type -AssemblyName System.Windows.Forms
        $message = 'Primera instalacion: RTX 4090 24 GB y controlador CUDA 13; Internet; hasta 42.470.585.471 bytes de modelos base (se reutilizan archivos verificados), mas 30 GB para runtime/cache; 120 GB libres recomendados. Lea licenses/ y THIRD_PARTY_NOTICES.md. La licencia H3 excluye EE.UU., UE, Reino Unido y Corea del Sur; alli se requiere autorizacion separada de MiniMax. BFS restringe reventa y servicios alojados. No requiere Claude, Hermes ni claves API. Acepta las licencias y las descargas fijadas?'
        $answer = [System.Windows.Forms.MessageBox]::Show($message, 'Kinjutsu - licencias y descargas', 'YesNo', 'Information')
        if ($answer -ne 'Yes') { throw 'Instalacion cancelada. No se han descargado modelos.' }
        # Preflight before downloading or executing bootstrap tools.
        $free = (Get-PSDrive -Name ([IO.Path]::GetPathRoot($root).Substring(0,1))).Free
        $manifest = Get-Content -LiteralPath (Join-Path $root 'models/manifest.json') -Raw | ConvertFrom-Json
        $needed = 30000000000L
        $roots = @((Join-Path $root 'models'))
        $rootsFile = Join-Path $root 'runtime/model-roots.json'
        if (Test-Path -LiteralPath $rootsFile) { $roots += @((Get-Content -LiteralPath $rootsFile -Raw | ConvertFrom-Json).roots) }
        foreach ($model in $manifest.models) {
            $verified = $false
            foreach ($folder in $roots) {
                foreach ($candidate in @((Join-Path $folder $model.target), (Join-Path $folder ([IO.Path]::GetFileName($model.target))))) {
                    if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and (Get-Item -LiteralPath $candidate).Length -eq [long]$model.size -and (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -eq $model.sha256) { $verified = $true; break }
                }
                if ($verified) { break }
            }
            if (-not $verified) { $needed += [long]$model.size }
        }
        if ($free -lt $needed) { throw 'Espacio insuficiente. Libere espacio en la unidad del paquete; 120 GB recomendados.' }
        if (-not (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue)) { throw 'Falta nvidia-smi. Instale el controlador NVIDIA compatible con CUDA 13 y reinicie.' }
        # HEAD tests only; immutable artifact/hash checks remain mandatory at download.
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        try { Invoke-WebRequest -UseBasicParsing -Method Head -Uri 'https://huggingface.co' -TimeoutSec 20 | Out-Null }
        catch { throw 'No hay acceso a Hugging Face. Compruebe Internet, proxy o firewall. Reintente INICIAR.' }
        & (Join-Path $PSScriptRoot 'Install-Kinjutsu.ps1') -InstallRoot $root -AcceptLicenses
        if ($LASTEXITCODE -ne 0) { throw 'Fallo de instalacion; revise runtime/logs/launcher.log y reintente.' }
    }
    Invoke-Kinjutsu $root 'launch'
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message)
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(('No se pudo iniciar Kinjutsu. ' + $_.Exception.Message + "`nLog: " + $log), 'Kinjutsu - accion requerida', 'OK', 'Error') | Out-Null
    exit 1
} finally { Stop-Transcript | Out-Null; if ($hasLock) { $mutex.ReleaseMutex() }; $mutex.Dispose() }
