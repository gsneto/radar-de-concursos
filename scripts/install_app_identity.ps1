# Radar de Concursos - registra a identidade do aplicativo para notificações nativas.
#
# Aplica o AppUserModelID "RadarDeConcursos.Radar" a um atalho no Menu Iniciar, requisito
# do Windows para que aplicativos desktop **não empacotados** exibam toasts.
# Idempotente: reexecutar atualiza o mesmo atalho, sem duplicar.
#
# Uso:
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_app_identity.ps1
[CmdletBinding()]
param(
    [string]$Aumid = "RadarDeConcursos.Radar",
    [string]$ShortcutName = "Radar de Concursos",
    [string]$ShortcutDir = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ShortcutDir)) {
    $Programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
} else {
    $Programs = $ShortcutDir
}
$Shortcut = Join-Path $Programs "$ShortcutName.lnk"
$Target = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path $Programs)) { New-Item -ItemType Directory -Path $Programs -Force | Out-Null }

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($Shortcut)
$lnk.TargetPath = $Target
$lnk.Arguments = "-NoProfile -WindowStyle Hidden -Command exit"
$lnk.Description = "Radar de Concursos - identidade de notificacao"
$lnk.Save()

# Define a propriedade System.AppUserModel.ID no atalho (requer o shell do Windows).
$code = @"
using System;
using System.Runtime.InteropServices;
public static class Aumid {
    [DllImport("shell32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern int SHGetPropertyStoreFromParsingName(
        string pszPath, IntPtr pbc, int flags, ref Guid riid, out IPropertyStore ppv);
    [DllImport("ole32.dll")]
    public static extern int PropVariantClear(ref PROPVARIANT pvar);
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPVARIANT {
        public ushort vt; public ushort wReserved1; public ushort wReserved2; public ushort wReserved3;
        public IntPtr p; public int p2;
    }
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore {
        int GetCount(out uint c);
        int GetAt(uint i, out PROPERTYKEY k);
        int GetValue(ref PROPERTYKEY k, out PROPVARIANT v);
        int SetValue(ref PROPERTYKEY k, ref PROPVARIANT v);
        int Commit();
    }
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPERTYKEY { public Guid fmtid; public uint pid; }
    public static void Set(string path, string aumid) {
        Guid iid = new Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99");
        IPropertyStore store;
        int hr = SHGetPropertyStoreFromParsingName(path, IntPtr.Zero, 2, ref iid, out store);
        if (hr != 0) throw new Exception("SHGetPropertyStore falhou: " + hr);
        PROPERTYKEY key = new PROPERTYKEY();
        key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"); // System.AppUserModel.ID
        key.pid = 5;
        PROPVARIANT pv = new PROPVARIANT();
        pv.vt = 31; // VT_LPWSTR
        pv.p = Marshal.StringToCoTaskMemUni(aumid);
        store.SetValue(ref key, ref pv);
        store.Commit();
        PropVariantClear(ref pv);
    }
}
"@
Add-Type -TypeDefinition $code -Language CSharp | Out-Null
[Aumid]::Set($Shortcut, $Aumid)

Write-Output "Identidade registrada: $Shortcut (AUMID=$Aumid)"
