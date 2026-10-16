# Radar de Concursos - instala as tarefas agendadas do Windows.
#
# Cria (ou atualiza, sem duplicar) tarefas com nomes estáveis:
#   "Radar de Concursos - Ciclo"     -> um ciclo operacional a cada N horas
#   "Radar de Concursos - Servidor"  -> servidor local no logon (opcional)
#
# Executa com a conta normal do usuário (sem senha armazenada). Não exige administrador.
# Configura "Ignorar nova instância" para não sobrepor ciclos e "Iniciar assim que
# possível após uma inicialização perdida" para recuperar após reinício.
#
# Uso:
#   pwsh -File .\scripts\install_tasks.ps1
#   pwsh -File .\scripts\install_tasks.ps1 -IntervalHours 4 -IncludeServer
[CmdletBinding()]
param(
    [int]$IntervalHours = 6,
    [switch]$IncludeServer,
    [string]$TaskPrefix = "Radar de Concursos",
    [string]$Config = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ConfigPath = if ($Config) { $Config } else { Join-Path $Root "radar_ops.json" }

# Python de bootstrap: ambiente -> venv do projeto -> `python` (só para criar o config).
function Get-BootstrapPython {
    if ($env:RADAR_PYTHON) { return $env:RADAR_PYTHON }
    $venv = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venv) { return $venv }
    return "python"
}

# Cria o config (sem segredos) se ainda não existir.
if (-not (Test-Path $ConfigPath)) {
    Push-Location $Root
    try { & (Get-BootstrapPython) -m radar ops-config --write --config $ConfigPath | Out-Null } finally { Pop-Location }
}

# Python validado: o do config (mesmo que a suíte usa), nunca `python` do PATH.
$Python = $env:RADAR_PYTHON
if (-not $Python) {
    Push-Location $Root
    try {
        $fromCfg = (& (Get-BootstrapPython) -c "import sys; from radar.ops_config import load_config; print(load_config(sys.argv[1] if len(sys.argv)>1 else None)['python'])" $ConfigPath 2>$null)
    } finally { Pop-Location }
    if ($fromCfg) { $Python = "$fromCfg".Trim() } else { $Python = Get-BootstrapPython }
}
if (-not (Test-Path $Python)) {
    throw "Python validado não encontrado: $Python (defina RADAR_PYTHON ou ajuste radar_ops.json)"
}
Write-Output "Python: $Python"

function Install-CycleTask {
    $name = "$TaskPrefix - Ciclo"
    $action = New-ScheduledTaskAction -Execute $Python `
        -Argument "-m radar ops-ciclo --config `"$ConfigPath`"" -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -Force `
        -Description "Radar de Concursos: ciclo operacional a cada $IntervalHours h (coleta + fila + alertas)." | Out-Null
    Write-Output "Tarefa registrada: $name (a cada $IntervalHours h)"
}

function Install-ServerTask {
    $name = "$TaskPrefix - Servidor"
    $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue)
    $shell = if ($pwsh) { $pwsh.Source } else { "powershell" }
    $action = New-ScheduledTaskAction -Execute $shell `
        -Argument "-NoProfile -File `"$PSScriptRoot\serve.ps1`" -Config `"$ConfigPath`"" -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -Force `
        -Description "Radar de Concursos: servidor local (loopback) no logon do usuário." | Out-Null
    Write-Output "Tarefa registrada: $name (no logon)"
}

Install-CycleTask
if ($IncludeServer) { Install-ServerTask }
Write-Output "Concluído. Verifique com: pwsh -File .\scripts\verify_tasks.ps1"
