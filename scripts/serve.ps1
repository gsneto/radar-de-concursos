# Radar de Concursos - inicia o servidor HTTP local (loopback) da interface.
#
# Uso:
#   pwsh -File .\scripts\serve.ps1                 # 127.0.0.1:8000
#   pwsh -File .\scripts\serve.ps1 -Port 8100
#
# O servidor liga apenas em loopback (nunca na rede pública). Não duplica a instância
# se a porta já estiver em uso.
[CmdletBinding()]
param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [string]$Config = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

# Já existe servidor nesta porta? Não inicia outro.
try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect($Host, $Port)
    $client.Close()
    Write-Output "Servidor já ativo em http://${Host}:${Port}/ - nada a fazer."
    exit 0
} catch { }

$Python = $env:RADAR_PYTHON
if (-not $Python) {
    $venv = Join-Path $Root ".venv\Scripts\python.exe"
    $probe = if (Test-Path $venv) { $venv } else { "python" }
    Push-Location $Root
    try {
        $fromCfg = (& $probe -c "import sys; from radar.ops_config import load_config; print(load_config(sys.argv[1] if len(sys.argv)>1 else None)['python'])" $Config 2>$null)
    } finally { Pop-Location }
    $Python = if ($fromCfg) { "$fromCfg".Trim() } else { $probe }
}

# Caminho do banco: do config (via python) para não divergir da coleta.
$Db = (& $Python -c "import json,sys; from radar.ops_config import load_config; print(load_config(sys.argv[1] if len(sys.argv)>1 else None)['db_path'])" $Config 2>$null)
if (-not $Db) { $Db = Join-Path $Root "data\radar.sqlite3" }

Push-Location $Root
try {
    & $Python -m radar serve --db $Db --host $Host --port $Port
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
