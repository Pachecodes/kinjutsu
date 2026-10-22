' Optional double-click launcher. Does not register any autostart entry.
Option Explicit
Dim fso, shell, folder, command
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & folder & "\Start-Kinjutsu.ps1" & Chr(34)
shell.Run command, 0, False
