# Radar de Concursos - executa UM ciclo operacional (coleta + fila + alertas).
#
# Uso:
#   pwsh -File .\scripts\run_cycle.ps1
#   pwsh -File .\scripts\run_cycle.ps1 -Limit 5
#
# O ciclo termina sozinho. Não fica residente. Usa o Python e o banco definidos em
# `radar_ops.json` (ou variáveis de ambiente RADAR_*).
[CmdletBinding()]
param(
    [int]$Limit = 0,
    [string]$Config = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

# Python: ambiente -> config (radar_ops.json) -> venv do projeto -> `python`.
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

$Args = @("-m", "radar", "ops-ciclo")
if ($Config) { $Args += @("--config", $Config) }
if ($Limit -gt 0) { $Args += @("--limit", "$Limit") }

Push-Location $Root
try {
    & $Python @Args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
