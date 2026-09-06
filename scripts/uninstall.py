import subprocess, winshell, os

def uninstall():
    # Remove scheduled tasks
    subprocess.run(["schtasks", "/delete", "/tn", "PHANTOM_Autostart", "/f"])
    subprocess.run(["schtasks", "/delete", "/tn", "PHANTOM_Ollama_Autostart", "/f"])
    
    # Remove Start Menu shortcut
    shortcut = os.path.join(winshell.start_menu(), "PHANTOM.lnk")
    if os.path.exists(shortcut):
        os.remove(shortcut)
    
    print("[OK] PHANTOM uninstalled cleanly.")

if __name__ == "__main__":
    uninstall()
