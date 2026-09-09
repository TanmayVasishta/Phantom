"""
Real OS actions for controlled mode — the deterministic, no-LLM path.

Everything here has to hold to one rule: controlled mode skips guardian_node
entirely (see route_after_mode), so nothing routed here gets risk-scored or
HITL-approved. That makes this file the wrong place for anything that
destroys data. Each action below is either read-only or trivially reversible
by the user (a radio toggle, a volume step, a brightness step, launching an
app, locking the screen). Closing an app is the one borderline case and is
handled with a graceful close request rather than a force-kill — see
close_app().
"""
from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RADIO_SCRIPT = os.path.join(os.path.dirname(_HERE), "scripts", "radio_control.ps1")

# Volume/brightness step sizes. A Windows volume-key tap moves the master
# volume by exactly 2%, which is what makes set_volume()'s "floor then climb"
# approach below land on the number the user actually asked for.
_VK_STEP_PERCENT = 2
_STEP_TAPS = 5              # a "volume up" nudges ~10%
_FLOOR_TAPS = 55            # > 50 taps guarantees 0% from any starting level

_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF
_KEYEVENTF_KEYUP = 0x0002

# Bare app words -> what actually launches them. Anything not listed falls
# through to the shell, which resolves PATH entries and registered app paths.
_APP_ALIASES = {
    "chrome": "chrome.exe", "google chrome": "chrome.exe",
    "edge": "msedge.exe", "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe", "brave": "brave.exe",
    "notepad": "notepad.exe", "calculator": "calc.exe", "calc": "calc.exe",
    "explorer": "explorer.exe", "file explorer": "explorer.exe",
    "terminal": "wt.exe", "cmd": "cmd.exe", "powershell": "powershell.exe",
    "vscode": "code", "vs code": "code", "code": "code",
    "spotify": "spotify.exe", "settings": "ms-settings:",
    "task manager": "taskmgr.exe", "paint": "mspaint.exe",
}


def _powershell(args: list[str], timeout: int = 25) -> tuple[bool, str]:
    """Run a PowerShell command, returning (ok, trimmed output)."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "timed out"
    except OSError as exc:
        return False, str(exc)
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return proc.returncode == 0, out


def _tap(vk: int, times: int = 1) -> None:
    user32 = ctypes.windll.user32
    for _ in range(times):
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, _KEYEVENTF_KEYUP, 0)


# ── radios ───────────────────────────────────────────────────────────────

def _radio(kind: str, action: str) -> tuple[bool, str]:
    ok, out = _powershell(["-File", _RADIO_SCRIPT, "-Kind", kind, "-Action", action])
    # The script always answers "OK|<state>" or "ERROR|<reason>" so a failure
    # reason survives back to the user instead of becoming a bare False.
    if "|" in out:
        tag, _, detail = out.partition("|")
        return tag.strip() == "OK", detail.strip()
    return ok, out or "no response from radio control"


def radio_state(kind: str) -> str:
    ok, detail = _radio(kind, "state")
    return detail if ok else f"unknown ({detail})"


def set_radio(kind: str, on: bool) -> str:
    label = "Bluetooth" if kind == "Bluetooth" else "Wi-Fi"
    ok, detail = _radio(kind, "on" if on else "off")
    if ok:
        return f"{label} is now {detail}."
    return f"Couldn't change {label}: {detail}"


# ── volume ───────────────────────────────────────────────────────────────

def volume_step(up: bool) -> str:
    _tap(_VK_VOLUME_UP if up else _VK_VOLUME_DOWN, _STEP_TAPS)
    return f"Volume {'up' if up else 'down'} ~{_STEP_TAPS * _VK_STEP_PERCENT}%."


def volume_mute(toggle_to_muted: bool | None = None) -> str:
    # The mute key is a toggle with no query, so "mute" and "unmute" both send
    # the same key; the wording below stays honest about that rather than
    # claiming a state it can't read back.
    _tap(_VK_VOLUME_MUTE)
    return "Toggled mute."


def set_volume(percent: int) -> str:
    """
    Drop to 0 then climb, because the volume keys are the only lever
    available without an audio-API dependency and they only move relatively.
    55 down-taps floors it from any level; each up-tap is a known 2%.
    """
    percent = max(0, min(100, int(percent)))
    _tap(_VK_VOLUME_DOWN, _FLOOR_TAPS)
    if percent:
        _tap(_VK_VOLUME_UP, round(percent / _VK_STEP_PERCENT))
    return f"Volume set to about {percent}%."


# ── brightness ───────────────────────────────────────────────────────────

def get_brightness() -> int | None:
    ok, out = _powershell([
        "-Command",
        "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness "
        "-ErrorAction Stop).CurrentBrightness",
    ])
    if not ok:
        return None
    match = re.search(r"\d+", out)
    return int(match.group()) if match else None


def set_brightness(percent: int) -> str:
    percent = max(0, min(100, int(percent)))
    # -InputObject on the fetched instance, NOT -ClassName. WmiSetBrightness is
    # an instance method: calling it statically fails with 'Type mismatch for
    # parameter "Brightness"' even on hardware that fully supports it —
    # verified on this machine, where the static form errored while the
    # instance form set the panel immediately.
    ok, out = _powershell([
        "-Command",
        "$i = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods "
        "-ErrorAction Stop; "
        f"Invoke-CimMethod -InputObject $i -MethodName WmiSetBrightness "
        f"-Arguments @{{Brightness={percent};Timeout=1}} -ErrorAction Stop | Out-Null; 'set'",
    ])
    if ok:
        return f"Brightness set to {percent}%."
    # Only reachable when the panel genuinely doesn't expose the WMI method —
    # most often an external monitor, which has no software brightness control.
    return ("Couldn't set brightness — this display doesn't expose software "
            f"brightness control ({out.splitlines()[0] if out else 'no detail'}).")


def brightness_step(up: bool) -> str:
    current = get_brightness()
    if current is None:
        return ("Couldn't read the current brightness — this display may not "
                "support software brightness control.")
    return set_brightness(max(0, min(100, current + (10 if up else -10))))


# ── apps / session ───────────────────────────────────────────────────────

def open_app(name: str) -> str:
    target = _APP_ALIASES.get(name.strip().lower(), name.strip())
    try:
        # `start ""` goes through the shell resolver, so registered app paths
        # and PATH entries both work without hardcoding install locations.
        subprocess.Popen(f'start "" "{target}"', shell=True)
        return f"Opening {name.strip()}."
    except OSError as exc:
        return f"Couldn't open {name.strip()}: {exc}"


def close_app(name: str) -> str:
    target = _APP_ALIASES.get(name.strip().lower(), name.strip())
    if not target.lower().endswith(".exe"):
        target += ".exe"
    # No /F. A forced kill discards unsaved work with no undo and no approval
    # step in front of it (controlled mode has no HITL); a plain taskkill
    # sends a close request, so the app gets to prompt about unsaved changes.
    ok, out = _powershell(["-Command", f"taskkill /IM \"{target}\""], timeout=15)
    if ok:
        return f"Asked {name.strip()} to close."
    if "not found" in out.lower():
        return f"{name.strip()} doesn't appear to be running."
    return f"Couldn't close {name.strip()}: {out.splitlines()[0] if out else 'unknown error'}"


def lock_screen() -> str:
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Locking the screen."
    except OSError as exc:
        return f"Couldn't lock the screen: {exc}"


# ── dispatcher ───────────────────────────────────────────────────────────

_RE_RADIO = re.compile(
    r"^\s*(?P<q>is|are|what'?s|whats)?\s*"
    r"(?:turn|switch|toggle)?\s*"
    r"(?P<a1>on|off|enable|disable)?\s*"
    r"(?:the\s+)?(?P<kind>bluetooth|bt|wi-?fi|wireless)"
    r"(?:\s+(?P<a2>on|off|status|state))?\s*\??\s*$",
    re.IGNORECASE,
)
_RE_VOLUME_SET = re.compile(
    r"^\s*(?:set|turn)\s+(?:the\s+)?volume\s+(?:to\s+)?(?P<pct>\d{1,3})\s*%?\s*$",
    re.IGNORECASE,
)
_RE_VOLUME_STEP = re.compile(
    r"^\s*(?:volume|sound)\s+(?P<dir>up|down)\s*$"
    r"|^\s*(?:turn\s+)?(?:the\s+)?(?:volume|sound)\s+(?P<dir2>up|down)\s*$",
    re.IGNORECASE,
)
_RE_MUTE = re.compile(r"^\s*(?:un)?mute(?:\s+the\s+(?:volume|sound))?\s*$", re.IGNORECASE)
_RE_BRIGHT_SET = re.compile(
    r"^\s*(?:set|turn)\s+(?:the\s+)?brightness\s+(?:to\s+)?(?P<pct>\d{1,3})\s*%?\s*$",
    re.IGNORECASE,
)
_RE_BRIGHT_STEP = re.compile(
    r"^\s*brightness\s+(?P<dir>up|down)\s*$"
    r"|^\s*(?P<verb>increase|decrease|raise|lower)\s+(?:the\s+)?brightness\s*$",
    re.IGNORECASE,
)
_RE_LOCK = re.compile(
    r"^\s*lock\s+(?:the\s+)?(?:screen|pc|computer|workstation|desktop)\s*$", re.IGNORECASE)
_RE_APP = re.compile(
    r"^\s*(?P<verb>open|launch|start|close|quit|exit|kill|stop)\s+(?P<app>[\w .+#-]+?)\s*$",
    re.IGNORECASE,
)


def execute(command: str) -> str | None:
    """
    Run a controlled-mode command. Returns the user-facing message, or None
    if this isn't an action we handle (caller falls back to its own reply).
    """
    cmd = (command or "").strip()
    if not cmd:
        return None

    if sys.platform != "win32":
        return None

    m = _RE_VOLUME_SET.match(cmd)
    if m:
        return set_volume(int(m.group("pct")))

    m = _RE_VOLUME_STEP.match(cmd)
    if m:
        return volume_step((m.group("dir") or m.group("dir2")).lower() == "up")

    if _RE_MUTE.match(cmd):
        return volume_mute()

    m = _RE_BRIGHT_SET.match(cmd)
    if m:
        return set_brightness(int(m.group("pct")))

    m = _RE_BRIGHT_STEP.match(cmd)
    if m:
        direction = m.group("dir") or m.group("verb")
        return brightness_step(direction.lower() in ("up", "increase", "raise"))

    if _RE_LOCK.match(cmd):
        return lock_screen()

    m = _RE_RADIO.match(cmd)
    if m:
        kind_word = m.group("kind").lower()
        kind = "Bluetooth" if kind_word in ("bluetooth", "bt") else "WiFi"
        label = "Bluetooth" if kind == "Bluetooth" else "Wi-Fi"
        action = (m.group("a1") or m.group("a2") or "").lower()

        # A leading "is"/"what's" makes it a question, so "is bluetooth on"
        # reports state instead of switching it on — the opposite of what the
        # words after it would otherwise trigger.
        if m.group("q") or action in ("status", "state"):
            return f"{label} is currently {radio_state(kind)}."
        if action in ("on", "enable"):
            return set_radio(kind, True)
        if action in ("off", "disable"):
            return set_radio(kind, False)
        return f"{label} is currently {radio_state(kind)}."

    m = _RE_APP.match(cmd)
    if m:
        verb, app = m.group("verb").lower(), m.group("app")
        # "turn off bluetooth" already matched above; anything reaching here
        # with a radio word is a phrasing we don't want to treat as an app.
        if app.strip().lower() in ("bluetooth", "wifi", "wi-fi", "wireless", "bt"):
            return None
        if verb in ("open", "launch", "start"):
            return open_app(app)
        return close_app(app)

    return None
