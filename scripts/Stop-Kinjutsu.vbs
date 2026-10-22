' Optional double-click launcher; stops only identity-matched Kinjutsu processes.
Option Explicit
Dim fso, shell, folder, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & folder & "\Stop-Kinjutsu.ps1" & Chr(34)
shell.Run command, 0, False
