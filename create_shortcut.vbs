' MessageCannon Desktop Shortcut Creator
' This script creates a desktop shortcut for MessageCannon

Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get the installation directory
strAppPath = objShell.RegRead("HKCU\Software\MessageCannon\InstallPath")
If strAppPath = "" Then
    ' Fallback to default locations
    strAppPath = objShell.SpecialFolders("AppData") & "\Programs\MessageCannon"
End If

If Not objFSO.FolderExists(strAppPath) Then
    ' Try portable path
    strAppPath = objFSO.GetParentFolderName(WScript.ScriptFullName) & "\MessageCannon_Portable"
End If

strExePath = strAppPath & "\MessageCannon.exe"
strIconPath = strAppPath & "\assets\icons\app.ico"
strDesktopPath = objShell.SpecialFolders("Desktop")
strLinkPath = strDesktopPath & "\MessageCannon.lnk"

' Check if exe exists
If objFSO.FileExists(strExePath) Then
    ' Create shortcut
    Set objLink = objShell.CreateShortCut(strLinkPath)
    objLink.TargetPath = strExePath
    objLink.Description = "MessageCannon - WhatsApp Bulk Messenger"
    
    ' Set icon if available
    If objFSO.FileExists(strIconPath) Then
        objLink.IconLocation = strIconPath & ", 0"
    End If
    
    objLink.WindowStyle = 1 ' Normal window
    objLink.WorkingDirectory = objFSO.GetParentFolderName(strExePath)
    objLink.Save
    
    MsgBox "Desktop shortcut created successfully!", 64, "MessageCannon"
Else
    MsgBox "MessageCannon.exe not found. Please install the application first.", 48, "Error"
End If
