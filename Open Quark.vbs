Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
root = files.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
shell.Run "pythonw """ & root & "\launch_gui.py""", 0, False
