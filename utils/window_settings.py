"""
Tiny persisted key/value store for a floating-overlay window's own UI state
(currently just the pin toggle). Shared between ui/phantom_window.py (v1,
phantom_memory/settings.json) and agent_v2/ui/window.py (v2,
agent_v2/data/settings.json) rather than each hand-rolling the same few
lines of JSON load/save.
"""
from __future__ import annotations

import json
import os


class WindowSettings:
    def __init__(self, path: str):
        self._path = path
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except Exception:
            # Missing file (first run) or corrupt JSON — start from defaults
            # rather than crashing window construction over a settings file.
            self._data = {}

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2)
        except Exception:
            pass  # a settings write failing must never break the UI action that triggered it
