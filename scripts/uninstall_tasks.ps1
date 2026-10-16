# Radar de Concursos - remove as tarefas agendadas (NÃO apaga dados do Radar).
#
# Uso:
#   pwsh -File .\scripts\uninstall_tasks.ps1
[CmdletBinding()]
param([string]$TaskPrefix = "Radar de Concursos")

$ErrorActionPreference = "Continue"
foreach ($name in @("$TaskPrefix - Ciclo", "$TaskPrefix - Servidor")) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Output "Removida: $name"
    } else {
        Write-Output "Não encontrada (nada a remover): $name"
    }
}
Write-Output "O banco, os logs e o histórico documental foram preservados."
exit 0
