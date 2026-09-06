@echo off
echo Installing PHANTOM...
echo.

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt -q

echo [2/4] Downloading spaCy model...
python -m spacy download en_core_web_sm -q

echo [3/4] Setting up Ollama autostart...
python scripts/install_ollama_service.py

echo [4/4] Creating Start Menu shortcut...
python scripts/create_shortcut.py

echo.
echo ✓ PHANTOM installed successfully!
echo ✓ Press Ctrl+Shift+P anytime to open PHANTOM.
echo ✓ Ollama starts automatically on login.
echo.
pause
