# Radar de Concursos - verifica as tarefas agendadas (estado real, não só existência).
#
# Uso:
#   pwsh -File .\scripts\verify_tasks.ps1
[CmdletBinding()]
param([string]$TaskPrefix = "Radar de Concursos")

$ErrorActionPreference = "Continue"
$names = @("$TaskPrefix - Ciclo", "$TaskPrefix - Servidor")
$any = $false

foreach ($name in $names) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if (-not $task) { Write-Output "AUSENTE: $name"; continue }
    $any = $true
    $info = Get-ScheduledTaskInfo -TaskName $name
    $state = $task.State
    $last = $info.LastRunTime
    $result = $info.LastTaskResult
    $next = $info.NextRunTime
    Write-Output "TAREFA : $name"
    Write-Output "  Estado        : $state"
    Write-Output "  Última exec.  : $last (resultado=$result)"
    Write-Output "  Próxima exec. : $next"
    $trigger = ($task.Triggers | ForEach-Object { $_.CimClass.CimClassName }) -join ", "
    Write-Output "  Disparadores  : $trigger"
    $settings = $task.Settings
    Write-Output "  Instância     : $($settings.MultipleInstances) | IniciarAtrasado: $($settings.StartWhenAvailable)"
}

if (-not $any) { Write-Output "Nenhuma tarefa do Radar encontrada. Rode install_tasks.ps1." }
exit 0
