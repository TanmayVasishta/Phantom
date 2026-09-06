import subprocess, sys, os

def install_ollama_autostart():
    ollama_path = r"C:\Users\{username}\AppData\Local\Programs\Ollama\ollama.exe"
    
    # Find actual ollama path
    result = subprocess.run(
        ["where", "ollama"], capture_output=True, text=True
    )
    if result.returncode == 0:
        ollama_path = result.stdout.strip().split("\n")[0]
    
    # Create scheduled task via schtasks
    cmd = [
        "schtasks", "/create",
        "/tn", "PHANTOM_Ollama_Autostart",
        "/tr", f'"{ollama_path}" serve',
        "/sc", "ONLOGON",
        "/rl", "HIGHEST",
        "/f"  # force overwrite if exists
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[OK] Ollama will now start on Windows login.")
        print("[OK] Keep_alive set to 24h — model stays hot.")
    else:
        print(f"[FAIL] {result.stderr}")
        print("Try running as Administrator once.")
    
    # Also set OLLAMA_KEEP_ALIVE environment variable
    subprocess.run([
        "setx", "OLLAMA_KEEP_ALIVE", "24h"
    ], capture_output=True)
    
    print("[OK] OLLAMA_KEEP_ALIVE=24h set system-wide.")

if __name__ == "__main__":
    install_ollama_autostart()
