import os
import sys

if sys.stdout is None or sys.stderr is None:
    try:
        fd = os.open("NUL", os.O_RDWR)
        os.dup2(fd, 0)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
    except Exception as e:
        pass

import PyQt6.QtWebEngineWidgets
open("webengine_ok.txt", "w").write("OK")
