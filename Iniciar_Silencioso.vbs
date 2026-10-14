Option Explicit

Dim shell, fso, root, logDir, logPath, env, command, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
logDir = root & "\data"
logPath = logDir & "\launcher.log"

If Not fso.FolderExists(logDir) Then
    On Error Resume Next
    fso.CreateFolder logDir
    If Err.Number <> 0 Then
        MsgBox "Não foi possível criar a pasta de registro do ClipLink.", 16, "ClipLink"
        WScript.Quit 1
    End If
    On Error GoTo 0
End If

Set env = shell.Environment("PROCESS")
env("CLIPLINK_HIDDEN_LAUNCH") = "1"

command = Chr(34) & shell.ExpandEnvironmentStrings("%ComSpec%") & Chr(34) & _
          " /d /c " & Chr(34) & Chr(34) & root & "\start_windows.bat" & Chr(34) & _
          " > " & Chr(34) & logPath & Chr(34) & " 2>&1"
exitCode = shell.Run(command, 0, True)

If exitCode <> 0 Then
    MsgBox "Não foi possível iniciar o ClipLink." & vbCrLf & vbCrLf & _
           "Consulte os detalhes em:" & vbCrLf & logPath, 16, "ClipLink"
End If
