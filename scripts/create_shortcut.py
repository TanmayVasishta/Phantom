import winshell
from win32com.client import Dispatch
import os
from pathlib import Path

def create_start_menu_shortcut():
    # pip install winshell pywin32
    
    start_menu = winshell.start_menu()
    shortcut_path = os.path.join(start_menu, "PHANTOM Agent.lnk")
    
    import sys
    python_exe = str(Path(sys.executable).parent / "python.exe")
    script_path = str(Path(__file__).parent.parent / "phantom_ui.py")
    vbs_path = str(Path(__file__).parent.parent / "launcher.vbs")
    with open(vbs_path, "w") as f:
        f.write('Set WshShell = CreateObject("WScript.Shell")\n')
        f.write(f'WshShell.Run """{python_exe}"" ""{script_path}""", 0, False\n')
        
    wscript_path = r"C:\Windows\System32\wscript.exe"
    
    shell = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.Targetpath = wscript_path
    shortcut.Arguments = f'"{vbs_path}"'
    shortcut.WorkingDirectory = str(Path(__file__).parent.parent)
    shortcut.IconLocation = str(Path(sys.executable).parent / "python.exe")
    shortcut.Description = "PHANTOM — Privacy-First AI"
    shortcut.save()
    
    print(f"[OK] Start Menu shortcut created.")
    print(f"     Search 'PHANTOM' in Start Menu.")

if __name__ == "__main__":
    create_start_menu_shortcut()
