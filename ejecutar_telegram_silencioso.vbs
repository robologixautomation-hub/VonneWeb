Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strPath = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strPath
WshShell.Run """C:\Users\PC3\AppData\Local\Programs\Python\Python312\pythonw.exe"" telegram_notifier.py --daemon", 0, False
Set WshShell = Nothing
