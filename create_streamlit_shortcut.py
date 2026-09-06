import os
import sys
import win32com.client

shell = win32com.client.Dispatch("WScript.Shell")
programs = shell.SpecialFolders("Programs")
shortcut = shell.CreateShortcut(os.path.join(programs, "PHANTOM Chat.lnk"))
shortcut.TargetPath = sys.executable
shortcut.Arguments = f'-m streamlit run "{os.path.join(os.path.dirname(__file__), "phantom_streamlit.py")}"'
shortcut.IconLocation = sys.executable
shortcut.Save()
print("Shortcut created at:", os.path.join(programs, "PHANTOM Chat.lnk"))
