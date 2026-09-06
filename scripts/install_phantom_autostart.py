import subprocess, os, sys
from pathlib import Path

def install_phantom_autostart():
    # Path to phantom_ui.exe (after PyInstaller build)
    # or phantom_ui.py for development
    phantom_exe = Path(sys.executable).parent / "phantom_ui.exe"
    
    if not phantom_exe.exists():
        # Dev mode: use pythonw (no console window)
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        script = Path(__file__).parent.parent / "phantom_ui.py"
        run_cmd = f'"{pythonw}" "{script}"'
    else:
        run_cmd = f'"{phantom_exe}"'
    
    cmd = [
        "schtasks", "/create",
        "/tn", "PHANTOM_Autostart",
        "/tr", run_cmd,
        "/sc", "ONLOGON",
        "/f"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[OK] PHANTOM will start on login (system tray).")
    else:
        print(f"[FAIL] {result.stderr}")

if __name__ == "__main__":
    install_phantom_autostart()
