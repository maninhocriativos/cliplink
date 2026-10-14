Option Explicit

Dim shell, fso, root, desktop, shortcut, shortcutPath, launcher, iconPath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = root & "\Iniciar_Silencioso.vbs"
iconPath = root & "\assets\cliplink.ico"

If Not fso.FileExists(launcher) Or Not fso.FileExists(iconPath) Then
    MsgBox "Não encontrei os arquivos do ClipLink. Extraia o pacote completo e tente novamente.", 16, "ClipLink"
    WScript.Quit 1
End If

desktop = shell.SpecialFolders("Desktop")
shortcutPath = desktop & "\ClipLink.lnk"
Set shortcut = shell.CreateShortcut(shortcutPath)
shortcut.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
shortcut.Arguments = Chr(34) & launcher & Chr(34)
shortcut.WorkingDirectory = root
shortcut.IconLocation = iconPath & ",0"
shortcut.Description = "Abrir o ClipLink sem janela do terminal"
shortcut.Save

MsgBox "Atalho ClipLink criado na área de trabalho." & vbCrLf & _
       "Use o novo ícone para abrir o aplicativo.", 64, "ClipLink"
