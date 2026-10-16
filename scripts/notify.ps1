# Radar de Concursos - emite uma notificação nativa (toast) do Windows.
#
# Requer Windows 10/11 e o AppUserModelID registrado por install_app_identity.ps1.
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File notify.ps1 `
#       -Title "Titulo" -Body "Texto" -Aumid "RadarDeConcursos.Radar" -Launch "http://127.0.0.1:8000/"
#
# Saída: uma linha JSON {"accepted":true|false,"error":"..."} para o chamador.
param(
    [Parameter(Mandatory = $true)][string]$Title,
    [Parameter(Mandatory = $true)][string]$Body,
    [string]$Aumid = "RadarDeConcursos.Radar",
    [string]$Launch = "",
    [string]$Tag = ""
)

$ErrorActionPreference = "Stop"
try {
    [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
    [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]

    $esc = { param($s) [System.Security.SecurityElement]::Escape($s) }
    $launchAttr = ""
    if ($Launch) {
        $launchAttr = ' activationType="protocol" launch="{0}"' -f (& $esc $Launch)
    }
    $xml = @"
<toast$launchAttr>
  <visual>
    <binding template="ToastGeneric">
      <text>$(& $esc $Title)</text>
      <text>$(& $esc $Body)</text>
    </binding>
  </visual>
</toast>
"@
    $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
    $doc.LoadXml($xml)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
    if ($Tag) { $toast.Tag = $Tag }
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($Aumid).Show($toast)
    Write-Output '{"accepted":true,"error":null}'
}
catch {
    $msg = $_.Exception.Message
    $json = @{ accepted = $false; error = "$msg" } | ConvertTo-Json -Compress
    Write-Output $json
    exit 1
}
