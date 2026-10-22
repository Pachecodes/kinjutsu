# Pachecodes : Kinjutsu portable bootstrap. No elevation, PATH/registry edits, or tasks.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Resolve-KinjutsuRoot([string]$InstallRoot) {
    if (-not $InstallRoot) { $InstallRoot = Split-Path $PSScriptRoot -Parent }
    $root = (Resolve-Path -LiteralPath $InstallRoot).Path
    if (-not (Test-Path -LiteralPath (Join-Path $root 'models/manifest.json'))) { throw 'InstallRoot must be the extracted complete Kinjutsu package, not an empty destination.' }
    return $root
}
function Set-KinjutsuEnvironment([string]$Root) {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $Root 'runtime/python'
    $env:UV_CACHE_DIR = Join-Path $Root 'runtime/cache/uv'
    $env:UV_PYTHON_PREFERENCE = 'only-managed'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONNOUSERSITE = '1'
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
    $env:PATH = (Join-Path $Root 'runtime/tools/node') + ';' + (Join-Path $Root 'runtime/tools/git/cmd') + ';' + $env:PATH
}
function Install-PinnedZip([string]$Root,[string]$Name,[string]$Url,[string]$Sha256,[string]$Probe,[string]$Nested='') {
    $destination = Join-Path $Root ('runtime/tools/' + $Name)
    $pin = (Get-Content -LiteralPath (Join-Path $Root 'runtime/tools-manifest.json') -Raw | ConvertFrom-Json).tools | Where-Object { $_.name -eq $Name }
    if (-not $pin -or $pin.url -ne $Url -or $pin.sha256 -ne $Sha256) { throw "Manifest de herramienta no coincide: $Name" }
    $receiptPath = Join-Path $destination 'bootstrap-receipt.json'
    if (Test-Path -LiteralPath (Join-Path $destination $Probe)) {
        if (-not (Test-Path -LiteralPath $receiptPath)) { throw "Falta recibo verificable de herramienta; inspeccione $destination" }
        $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
        if ($receipt.archive_sha256 -ne $Sha256) { throw "Herramienta de otra version: $Name" }
        foreach ($file in $receipt.files) {
            if ($file.path -match '(^|[/\\])\.\.([/\\]|$)|:|^[/\\]') { throw 'Recibo inseguro' }
            $path = Join-Path $destination $file.path
            if (-not (Test-Path -LiteralPath $path) -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw "Herramienta alterada: $Name/$($file.path)" }
        }
        return
    }
    if (Test-Path -LiteralPath $destination) { throw "Incomplete tool directory exists; inspect manually: $destination" }
    $cache = Join-Path $Root 'runtime/cache/bootstrap'
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $archive = Join-Path $cache ($Name + '.zip')
    if (-not (Test-Path -LiteralPath $archive)) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $part = $archive + '.part'
        $offset = 0L
        if (Test-Path -LiteralPath $part) { $offset = (Get-Item -LiteralPath $part).Length }
        if ($offset -gt [long]$pin.size) { throw "Parcial demasiado grande: $Name" }
        if ($offset -lt [long]$pin.size) {
            Write-Host "Descargando herramienta fijada: $Name ($offset / $($pin.size) bytes)"
            $request = [Net.HttpWebRequest]::Create($Url)
            $request.Timeout = 120000
            $request.UserAgent = 'Kinjutsu-Installer/1'
            if ($offset -gt 0) { $request.AddRange($offset) }
            $response = $request.GetResponse()
            try {
                $append = [int]$response.StatusCode -eq 206
                if ($append -and $response.Headers['Content-Range'] -ne "bytes $offset-$([long]$pin.size - 1)/$($pin.size)") { throw 'Content-Range incorrecto; parcial conservado' }
                $mode = [IO.FileMode]::Create
                if ($append) { $mode = [IO.FileMode]::Append }
                $out = [IO.File]::Open($part, $mode, [IO.FileAccess]::Write, [IO.FileShare]::None)
                try {
                    $stream = $response.GetResponseStream()
                    $buffer = New-Object byte[] 1048576
                    while (($read = $stream.Read($buffer,0,$buffer.Length)) -gt 0) {
                        if ($out.Position + $read -gt [long]$pin.size) { throw 'Descarga excede tamano fijado' }
                        $out.Write($buffer,0,$read)
                    }
                } finally { $out.Dispose() }
            } finally { $response.Close() }
        }
        if ((Get-Item -LiteralPath $part).Length -ne [long]$pin.size -or (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Sha256) { throw "Tamano/SHA256 incorrecto: $Name; parcial conservado" }
        Move-Item -LiteralPath ($archive + '.part') -Destination $archive
    }
    if ((Get-Item -LiteralPath $archive).Length -ne [long]$pin.size -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Sha256) { throw "Cached tool hash mismatch: $Name" }
    $staging = Join-Path $cache ($Name + '-extract-' + [guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $archive -DestinationPath $staging
    $parent = Split-Path $destination -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    if ($Nested) { Move-Item -LiteralPath (Join-Path $staging $Nested) -Destination $destination; Remove-Item -LiteralPath $staging }
    else { Move-Item -LiteralPath $staging -Destination $destination }
    if (-not (Test-Path -LiteralPath (Join-Path $destination $Probe))) { throw "Tool archive layout unexpected: $Name" }
    $files = @(Get-ChildItem -LiteralPath $destination -File -Recurse | ForEach-Object { [ordered]@{path=$_.FullName.Substring($destination.Length+1).Replace('\','/');size=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} })
    [ordered]@{url=$Url;size=$pin.size;archive_sha256=$Sha256;files=$files} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
}
function Initialize-KinjutsuTools([string]$Root) {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows x64 is required.' }
    # Immutable release asset verified against GitHub's SHA256 and local extraction.
    Install-PinnedZip $Root 'ffmpeg' 'https://github.com/GyanD/codexffmpeg/releases/download/8.0/ffmpeg-8.0-essentials_build.zip' '647e467caf82b9fa200a562769b5ff4d736aaf725804ed2c64ea9752106fa569' 'bin/ffmpeg.exe' 'ffmpeg-8.0-essentials_build'
    if (-not (Test-Path -LiteralPath (Join-Path $Root 'runtime/tools/ffmpeg/bin/ffprobe.exe'))) { throw 'Portable FFmpeg installation is incomplete (ffprobe.exe missing); inspect runtime/tools/ffmpeg and rerun installer.' }
    Install-PinnedZip $Root 'uv' 'https://github.com/astral-sh/uv/releases/download/0.11.22/uv-x86_64-pc-windows-msvc.zip' 'b56939bac92d29996d351647f7c6f15b31cc69cf952d06d136de3e1e62eb64d1' 'uv.exe'
    Install-PinnedZip $Root 'git' 'https://github.com/git-for-windows/git/releases/download/v2.56.0.windows.2/MinGit-2.56.0.2-64-bit.zip' 'da35e72aa21c005a5a0d298cfbae110bc1609a815730ea0dde84b01a1b3cd3be' 'cmd/git.exe'
}
function Invoke-Kinjutsu([string]$Root,[string]$Command,[string[]]$Extra=@()) {
    Set-KinjutsuEnvironment $Root
    $python = Join-Path $Root 'runtime/venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw 'Run Install-Kinjutsu.ps1 first. For offline package checks use Verify-Kinjutsu.ps1 -PackageOnly with Python 3.12 available.' }
    & $python -s (Join-Path $Root 'scripts/kinjutsu.py') $Command --root $Root @Extra
    if ($LASTEXITCODE -ne 0) { throw "Kinjutsu $Command failed (exit $LASTEXITCODE)." }
}
