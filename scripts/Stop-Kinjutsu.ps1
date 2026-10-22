[CmdletBinding()]
param([string]$InstallRoot)
. (Join-Path $PSScriptRoot 'Common-Kinjutsu.ps1')
$root = Resolve-KinjutsuRoot $InstallRoot
try {
    if (-not (Test-Path -LiteralPath (Join-Path $root 'runtime/venv/Scripts/python.exe'))) {
        Write-Host 'Sin runtime instalado: no hay servicios propios para detener.'
        exit 0
    }
    Invoke-Kinjutsu $root 'stop'
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(('No se pudieron detener todos los procesos propios. No se ha terminado ningun proceso ajeno. ' + $_.Exception.Message + ' Revise runtime/logs/.'), 'Kinjutsu - detener', 'OK', 'Error') | Out-Null
    exit 1
}
