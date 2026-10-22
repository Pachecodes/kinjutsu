[CmdletBinding()]
param([string]$InstallRoot)
. (Join-Path $PSScriptRoot 'Common-Kinjutsu.ps1')
$root = Resolve-KinjutsuRoot $InstallRoot
Invoke-Kinjutsu $root 'verify'
Invoke-Kinjutsu $root 'start'
