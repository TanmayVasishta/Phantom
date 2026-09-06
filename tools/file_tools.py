"""
PHANTOM local tools — the actions the agent can actually perform.

Every tool returns a plain dict and never raises: the LLM needs to read the
failure and recover, and an exception inside a tool node aborts the whole
graph turn (which the user sees as an empty response).

Destructive tools are listed in HIGH_RISK_TOOLS and are routed through the
HITL approval gate before they execute.
"""

from langchain_core.tools import tool
import os
from pathlib import Path

# ── Path handling ─────────────────────────────────────────────────────────────

def _aliases() -> dict[str, Path]:
    home = Path.home()
    return {
        "downloads": home / "Downloads",
        "download": home / "Downloads",
        "desktop": home / "Desktop",
        "documents": home / "Documents",
        "docs": home / "Documents",
        "pictures": home / "Pictures",
        "photos": home / "Pictures",
        "music": home / "Music",
        "videos": home / "Videos",
        "home": home,
        "user folder": home,
        "phantom outputs": home / "Documents" / "PHANTOM_Outputs",
    }


# Where bare filenames (no directory given) are written.
OUTPUT_DIR = Path.home() / "Documents" / "PHANTOM_Outputs"


def resolve_path(path: str) -> Path:
    """
    Resolve a user-supplied path or folder alias to a concrete Path.

    Handles the ways people actually phrase it: "Downloads", "my downloads
    folder", "downloads/reports", "~/Desktop", quoted paths, trailing
    slashes. Raises ValueError on empty input rather than silently
    resolving to the current working directory.
    """
    if path is None:
        raise ValueError("No path was provided.")

    raw = str(path).strip().strip('"').strip("'")
    if not raw:
        raise ValueError("No path was provided.")

    key = raw.lower().replace("\\", "/").rstrip("/").strip()
    for prefix in ("my ", "the ", "./"):
        while key.startswith(prefix):
            key = key[len(prefix):].strip()
    for suffix in (" folder", " directory", " dir"):
        if key.endswith(suffix):
            key = key[: -len(suffix)].strip()

    aliases = _aliases()
    if key in aliases:
        return aliases[key]

    # "downloads/reports" → <home>/Downloads/reports
    head, sep, tail = key.partition("/")
    if sep and head in aliases and tail:
        return aliases[head] / tail

    return Path(raw).expanduser().resolve()


def is_safe_path(p: Path) -> bool:
    """Block access to protected OS directories."""
    try:
        resolved = str(p.resolve()).lower()
    except Exception:
        resolved = str(p).lower()

    blocked_roots = []
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    blocked_roots.append(str(Path(system_root)).lower())
    for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        val = os.environ.get(env_var)
        if val:
            blocked_roots.append(str(Path(val)).lower())

    return not any(resolved.startswith(root) for root in blocked_roots if root)


def _public_folder_hint(p_obj: Path) -> str:
    """
    Warn when a listing landed in C:\\Users\\Public — almost always a wrong guess.

    The model sometimes invents "C:\\Users\\Public\\Videos" for "my videos".
    That path exists and is near-empty, so the answer looks confidently correct
    while describing a folder the user never meant. Rather than silently
    redirecting (which would hide what was actually read), report the real
    result plus a hint so the agent can correct itself.
    """
    try:
        parts = [seg.lower() for seg in p_obj.parts]
        if "public" not in parts:
            return ""
        personal = Path.home() / p_obj.name
        if not personal.exists() or personal == p_obj:
            return ""
        try:
            n = sum(1 for _ in personal.iterdir())
        except OSError:
            return ""
        return (
            f"NOTE: this is the shared Public folder. The user's own folder "
            f"'{personal}' exists and holds {n} item(s). If the user said "
            f"'my {p_obj.name.lower()}' or just '{p_obj.name.lower()}', re-run "
            f"this tool with path='{p_obj.name.lower()}' and report that instead."
        )
    except Exception:
        return ""


def _is_protected_root(p_obj: Path) -> bool:
    """
    True for paths that must never be deleted wholesale, even though they
    aren't under a blocked system root: the user's home folder, a drive
    root, or one of the standard alias folders itself (Downloads, Desktop,
    etc.) — "delete downloads" almost always means its contents, not the
    folder object, and deleting the folder itself would take out something
    Windows and other apps expect to exist.
    """
    try:
        resolved = p_obj.resolve()
    except Exception:
        resolved = p_obj

    if resolved == Path.home().resolve():
        return True
    if resolved.parent == resolved:  # drive root, e.g. C:\
        return True
    for alias_target in _aliases().values():
        try:
            if resolved == alias_target.resolve():
                return True
        except Exception:
            continue
    return False


def _guard(p_obj: Path, must_exist: bool = True, expect: str | None = None) -> dict | None:
    """Shared validation. Returns an error dict, or None when the path is usable."""
    if not is_safe_path(p_obj):
        return {"error": f"Blocked for safety — protected system location: {p_obj}"}
    if must_exist and not p_obj.exists():
        return {"error": f"Path not found: {p_obj}"}
    if must_exist and expect == "dir" and not p_obj.is_dir():
        return {"error": f"Not a directory: {p_obj}"}
    if must_exist and expect == "file" and not p_obj.is_file():
        return {"error": f"Not a file: {p_obj}"}
    return None


# ── Read-only tools ───────────────────────────────────────────────────────────

@tool
def scan_directory(path: str) -> dict:
    """
    Scan a directory recursively and return files with their sizes.

    For a standard user folder pass the bare alias — "downloads", "desktop",
    "documents", "videos", "pictures", "music", "home" — which resolves to the
    current user's own folder. Do not pass C:\\Users\\Public\\... paths.
    """
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    files = []
    total_bytes = 0
    try:
        for f in p_obj.rglob("*"):
            try:
                if f.is_file():
                    size = f.stat().st_size
                    total_bytes += size
                    files.append({"path": str(f), "name": f.name, "size": size})
            except OSError:
                continue
    except OSError as e:
        return {"error": f"Could not scan {p_obj}: {e}"}

    total_count = len(files)
    truncated = total_count > 50
    result = {
        "files": files[:50],
        "count": total_count,
        "path": str(p_obj),
        "total_size_human": f"{total_bytes / 1024 / 1024:.1f} MB",
        "warning": (
            f"Showing first 50 of {total_count} files (truncated to protect the token budget)."
            if truncated else ""
        ),
    }
    hint = _public_folder_hint(p_obj)
    if hint:
        result["hint"] = hint
    return result


@tool
def list_directory(path: str) -> dict:
    """
    List the immediate contents of a directory (files and subfolders).

    For a standard user folder pass the bare alias — "downloads", "desktop",
    "documents", "videos", "pictures", "music", "home" — which resolves to the
    current user's own folder. Do not pass C:\\Users\\Public\\... paths.
    """
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    items = []
    try:
        for item in p_obj.iterdir():
            try:
                items.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            except OSError:
                continue
    except PermissionError:
        return {"error": f"Permission denied reading: {p_obj}"}
    except OSError as e:
        return {"error": f"Could not list {p_obj}: {e}"}

    total = len(items)
    result = {
        "items": items[:100],
        "count": total,
        "path": str(p_obj),
        "warning": f"Showing first 100 of {total} entries." if total > 100 else "",
    }
    hint = _public_folder_hint(p_obj)
    if hint:
        result["hint"] = hint
    return result


@tool
def read_file(path: str) -> dict:
    """Read the contents of a text file (first 5000 characters)."""
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="file")
    if err:
        return err

    try:
        if p_obj.stat().st_size > 10 * 1024 * 1024:
            return {"error": f"File too large to read ({p_obj.stat().st_size / 1024 / 1024:.1f} MB)."}
        content = p_obj.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return {"error": f"Permission denied reading: {p_obj}"}
    except OSError as e:
        return {"error": f"Could not read {p_obj}: {e}"}

    return {
        "content": content[:5000],
        "path": str(p_obj),
        "truncated": len(content) > 5000,
    }


@tool
def search_files(
    path: str,
    name_contains: str = "",
    extension: str = "",
    content_contains: str = "",
    min_size_mb: float = 0.0,
    max_size_mb: float = 0.0,
    modified_within_days: int = 0,
) -> dict:
    """
    Search a folder recursively for files matching any combination of filters.
    Leave a filter at its default (empty string / 0) to skip it.

    - name_contains: substring to match in the filename (case-insensitive)
    - extension: file extension without the dot, e.g. "pdf", "jpg"
    - content_contains: text that must appear inside the file (text files only,
      skips files over 2MB or that look binary — slower, use with a narrower
      folder/extension filter when possible)
    - min_size_mb / max_size_mb: size range in megabytes
    - modified_within_days: only files modified in the last N days

    Use this whenever the user names criteria instead of exact paths — e.g.
    "find all PDFs over 10MB in downloads", "find files with 'invoice' in the
    name", "find screenshots from the last week". Feed the returned paths
    straight into delete_files, move_file, or copy_file.
    """
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    import time as _time
    now = _time.time()
    ext_filter = extension.strip().lstrip(".").lower() if extension else ""
    name_filter = name_contains.strip().lower() if name_contains else ""
    content_filter = content_contains.strip().lower() if content_contains else ""
    min_bytes = min_size_mb * 1024 * 1024 if min_size_mb else 0
    max_bytes = max_size_mb * 1024 * 1024 if max_size_mb else None
    max_age_seconds = modified_within_days * 86400 if modified_within_days else None

    matches = []
    scanned = 0
    try:
        for f in p_obj.rglob("*"):
            try:
                if not f.is_file():
                    continue
                scanned += 1
                if scanned > 20000:
                    break  # safety cap on huge trees

                if name_filter and name_filter not in f.name.lower():
                    continue
                if ext_filter and f.suffix.lstrip(".").lower() != ext_filter:
                    continue

                st = f.stat()
                if st.st_size < min_bytes:
                    continue
                if max_bytes is not None and st.st_size > max_bytes:
                    continue
                if max_age_seconds is not None and (now - st.st_mtime) > max_age_seconds:
                    continue

                if content_filter:
                    if st.st_size > 2 * 1024 * 1024:
                        continue
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                    except (OSError, UnicodeDecodeError):
                        continue
                    if content_filter not in text.lower():
                        continue

                matches.append({
                    "path": str(f),
                    "name": f.name,
                    "size": st.st_size,
                    "modified": __import__("datetime").datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                })
            except OSError:
                continue
    except OSError as e:
        return {"error": f"Could not search {p_obj}: {e}"}

    total = len(matches)
    if total == 0:
        return {"count": 0, "message": f"No files matched in {p_obj}."}

    truncated = total > 50
    return {
        "matches": matches[:50],
        "count": total,
        "path": str(p_obj),
        "warning": f"Showing first 50 of {total} matches." if truncated else "",
    }


@tool
def find_duplicates(path: str) -> dict:
    """Find Windows-style duplicate files (e.g. 'report (1).pdf') in a folder."""
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    duplicates = _get_duplicates_list(path)

    total_wasted = 0
    paths = []
    for d in duplicates:
        try:
            total_wasted += d.stat().st_size
        except OSError:
            pass
        paths.append(str(d))

    if not paths:
        return {
            "total_duplicates_found": 0,
            "message": f"No duplicate files found in {p_obj}.",
        }

    return {
        "paths_to_delete_sample": paths[:10],
        "total_duplicates_found": len(paths),
        "wasted_human": f"{total_wasted / 1024 / 1024:.1f} MB",
        "action_required": (
            "To remove these, call delete_all_duplicates(path) — do NOT pass the "
            "list to delete_files, that would blow the token budget."
        ),
    }


@tool
def read_clipboard() -> dict:
    """Read the current clipboard contents."""
    try:
        import pyperclip
    except ImportError:
        return {"error": "Clipboard unavailable — pyperclip is not installed."}
    try:
        return {"content": pyperclip.paste()[:5000]}
    except Exception as e:
        return {"error": f"Could not read clipboard: {e}"}


@tool
def open_file(path: str) -> dict:
    """Open a file or folder with its default Windows application."""
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj)
    if err:
        return err

    try:
        os.startfile(str(p_obj))  # noqa: S606 — Windows shell open
    except AttributeError:
        import subprocess
        try:
            subprocess.Popen(["xdg-open", str(p_obj)])
        except Exception as e:
            return {"error": f"Could not open {p_obj}: {e}"}
    except OSError as e:
        return {"error": f"Could not open {p_obj}: {e}"}

    return {"opened": str(p_obj), "status": "success"}


# ── Organization tools (move / copy / rename / create folder) ────────────────
# None of these need HITL: each refuses outright rather than silently
# overwriting an existing destination, so there's no data-loss path — the
# same guarantee write_file already relies on.

def _refuse_if_destination_exists(dest: Path) -> dict | None:
    if dest.exists():
        return {
            "error": (
                f"'{dest}' already exists. Choose a different name/location, "
                f"or ask the user whether to delete/replace it first."
            )
        }
    return None


@tool
def move_file(source: str, destination: str) -> dict:
    """
    Move a file or folder to a new location (or use it to rename by giving a
    different final path component). If the destination is an existing
    folder, the source is moved inside it, keeping its original name.
    Refuses if the destination already exists — never overwrites.
    """
    import shutil

    try:
        src = resolve_path(source)
        dst = resolve_path(destination)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(src)
    if err:
        return err
    if not is_safe_path(dst):
        return {"error": f"Blocked for safety — protected system location: {dst}"}
    if _is_protected_root(src):
        return {"error": f"Refusing to move a protected top-level folder: {src}"}

    final_dst = (dst / src.name) if dst.is_dir() else dst
    err = _refuse_if_destination_exists(final_dst)
    if err:
        return err

    try:
        final_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(final_dst))
    except PermissionError:
        return {"error": f"Permission denied moving {src} (file may be open)."}
    except OSError as e:
        return {"error": f"Could not move {src} to {final_dst}: {e}"}

    return {"status": "success", "from": str(src), "to": str(final_dst)}


@tool
def copy_file(source: str, destination: str) -> dict:
    """
    Copy a file, or a folder recursively, to a new location. If the
    destination is an existing folder, the copy is placed inside it, keeping
    its original name. Refuses if the destination already exists.
    """
    import shutil

    try:
        src = resolve_path(source)
        dst = resolve_path(destination)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(src)
    if err:
        return err
    if not is_safe_path(dst):
        return {"error": f"Blocked for safety — protected system location: {dst}"}

    final_dst = (dst / src.name) if dst.is_dir() else dst
    err = _refuse_if_destination_exists(final_dst)
    if err:
        return err

    try:
        final_dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, final_dst)
        else:
            shutil.copy2(src, final_dst)
    except PermissionError:
        return {"error": f"Permission denied copying {src}."}
    except OSError as e:
        return {"error": f"Could not copy {src} to {final_dst}: {e}"}

    return {"status": "success", "from": str(src), "to": str(final_dst)}


@tool
def rename_file(path: str, new_name: str) -> dict:
    """
    Rename a file or folder in place (stays in the same parent directory).
    Pass just the new filename, not a full path. Refuses if a file with the
    new name already exists.
    """
    new_name = (new_name or "").strip().strip('"').strip("'")
    if not new_name:
        return {"error": "No new name was provided."}
    if "/" in new_name or "\\" in new_name:
        return {"error": "new_name must be a plain filename, not a path. Use move_file to relocate it."}

    try:
        src = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(src)
    if err:
        return err
    if _is_protected_root(src):
        return {"error": f"Refusing to rename a protected top-level folder: {src}"}

    dst = src.parent / new_name
    err = _refuse_if_destination_exists(dst)
    if err:
        return err

    try:
        src.rename(dst)
    except PermissionError:
        return {"error": f"Permission denied renaming {src} (file may be open)."}
    except OSError as e:
        return {"error": f"Could not rename {src}: {e}"}

    return {"status": "success", "from": str(src), "to": str(dst)}


@tool
def create_folder(path: str) -> dict:
    """Create a new folder, including any missing parent folders."""
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    if not is_safe_path(p_obj):
        return {"error": f"Blocked for safety — protected system location: {p_obj}"}
    if p_obj.exists():
        return {"error": f"'{p_obj}' already exists."}

    try:
        p_obj.mkdir(parents=True)
    except PermissionError:
        return {"error": f"Permission denied creating: {p_obj}"}
    except OSError as e:
        return {"error": f"Could not create {p_obj}: {e}"}

    return {"status": "success", "path": str(p_obj)}


# ── Duplicate detection ───────────────────────────────────────────────────────

def _get_duplicates_list(path: str) -> list[Path]:
    import re
    from collections import defaultdict

    try:
        path_obj = resolve_path(path)
    except ValueError:
        return []
    if not is_safe_path(path_obj) or not path_obj.exists() or not path_obj.is_dir():
        return []

    # Matches exactly ONE trailing " (N)" copy-suffix at the end of a stem.
    # Applied iteratively below — a file can legitimately carry more than
    # one, e.g. Windows saves a second copy of "Report (2).pdf" as
    # "Report (2) (1).pdf". Only stripping one suffix made that file's
    # "original" resolve to "Report.pdf" (which may not exist) while
    # "Report (2).pdf" also stripped to "Report.pdf" — the two never landed
    # in the same group, so neither was ever reported as a duplicate.
    suffix_pattern = re.compile(r"^(.*?)\s*\((\d+)\)$")
    groups = defaultdict(list)

    for f in path_obj.rglob("*"):
        try:
            if not f.is_file():
                continue
        except OSError:
            continue

        stem = f.stem
        strip_count = 0
        last_num = 0
        while True:
            m = suffix_pattern.match(stem)
            if not m:
                break
            stem = m.group(1)
            last_num = int(m.group(2))
            strip_count += 1

        canonical_name = stem + f.suffix
        groups[(f.parent, canonical_name)].append((f, strip_count, last_num))

    duplicates_to_delete = []
    for _key, entries in groups.items():
        if len(entries) <= 1:
            continue
        # Keep the "most original": fewest stripped suffixes (an exact
        # canonical match has 0), then lowest copy number as tiebreaker.
        entries.sort(key=lambda e: (e[1], e[2]))
        for f, _sc, _n in entries[1:]:
            duplicates_to_delete.append(f)

    return duplicates_to_delete


# ── Write / destructive tools (HITL-gated) ────────────────────────────────────

@tool
def write_file(path: str, content: str) -> dict:
    """
    Create a new file with the given content — HTML pages, notes, reports, CSV.

    Use this to build small HTML pages or text documents from a prompt. Pass a
    bare filename (e.g. 'summary.html') to save into the PHANTOM outputs folder,
    or a full path to choose the location. Never overwrites an existing file.
    """
    if content is None:
        return {"error": "No content was provided to write."}

    raw = (path or "").strip().strip('"').strip("'")
    if not raw:
        return {"error": "No filename was provided."}

    has_dir = ("/" in raw) or ("\\" in raw)
    try:
        p_obj = (OUTPUT_DIR / raw) if not has_dir else resolve_path(raw)
    except ValueError as e:
        return {"error": str(e)}

    if not is_safe_path(p_obj):
        return {"error": f"Blocked for safety — protected system location: {p_obj}"}

    if p_obj.exists():
        return {
            "error": (
                f"'{p_obj}' already exists. Choose a different filename, or ask the "
                f"user whether to delete the existing file first."
            )
        }

    try:
        p_obj.parent.mkdir(parents=True, exist_ok=True)
        p_obj.write_text(content, encoding="utf-8")
    except PermissionError:
        return {"error": f"Permission denied writing to: {p_obj}"}
    except OSError as e:
        return {"error": f"Could not write {p_obj}: {e}"}

    return {
        "status": "success",
        "path": str(p_obj),
        "bytes_written": len(content.encode("utf-8")),
        "note": f"File created at {p_obj}. Use open_file to view it.",
    }


@tool
def draft_email(to: str = "", subject: str = "", body: str = "") -> dict:
    """
    Open a Gmail compose window pre-filled with a recipient, subject and body.

    Prepares the email for review — it never sends. The user reads it in Gmail
    and presses send themselves. Requires HITL approval before the window opens.
    """
    import urllib.parse
    import webbrowser

    to = (to or "").strip()
    subject = (subject or "").strip()
    body = body or ""

    if not subject and not body:
        return {"error": "Nothing to draft — provide at least a subject or a body."}

    params = {"view": "cm", "fs": "1"}
    if to:
        params["to"] = to
    if subject:
        params["su"] = subject
    if body:
        params["body"] = body

    url = "https://mail.google.com/mail/?" + urllib.parse.urlencode(params)

    try:
        opened = webbrowser.open(url)
    except Exception as e:
        return {"error": f"Could not open the browser: {e}", "compose_url": url}

    if not opened:
        return {
            "status": "browser_not_opened",
            "compose_url": url,
            "note": "Could not launch a browser automatically. Open this URL manually.",
        }

    return {
        "status": "draft_opened",
        "to": to or "(not set)",
        "subject": subject,
        "body_preview": body[:200],
        "note": "Gmail compose window opened with the draft ready. NOT sent — the user reviews and sends it.",
    }


@tool
def delete_files(file_paths: list[str]) -> dict:
    """Delete specific files by path. Requires HITL approval."""
    if not file_paths:
        return {"error": "No file paths were provided."}
    if isinstance(file_paths, str):
        file_paths = [file_paths]

    deleted, failed = [], []
    for p in file_paths:
        try:
            p_obj = resolve_path(p)
        except ValueError as e:
            failed.append({"path": str(p), "error": str(e)})
            continue

        if not is_safe_path(p_obj):
            failed.append({"path": str(p), "error": "Blocked by system path safety policy."})
            continue
        if p_obj.is_dir():
            failed.append({"path": str(p), "error": "Refusing to delete a directory."})
            continue
        if not p_obj.exists():
            failed.append({"path": str(p), "error": "File not found."})
            continue

        try:
            os.remove(p_obj)
            deleted.append(str(p_obj))
        except PermissionError:
            failed.append({"path": str(p), "error": "Permission denied (file may be open)."})
        except OSError as e:
            failed.append({"path": str(p), "error": str(e)})

    return {
        "deleted": deleted,
        "failed": failed,
        "count_deleted": len(deleted),
        "count_failed": len(failed),
    }


@tool
def delete_all_duplicates(path: str) -> dict:
    """
    Delete all Windows-style numbered duplicates (e.g. 'file (1).txt') in a
    folder, keeping the original of each. Requires HITL approval.
    """
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    duplicates = _get_duplicates_list(path)
    if not duplicates:
        return {"message": f"No duplicates found in {p_obj}.", "deleted_count": 0}

    deleted, failed, freed = [], [], 0
    for p in duplicates:
        try:
            size = p.stat().st_size if p.exists() else 0
            os.remove(p)
            deleted.append(str(p))
            freed += size
        except PermissionError:
            failed.append({"path": str(p), "error": "Permission denied (file may be open)."})
        except OSError as e:
            failed.append({"path": str(p), "error": str(e)})

    return {
        "deleted_count": len(deleted),
        "deleted_sample": deleted[:10],
        "failed_count": len(failed),
        "failed": failed[:5],
        "freed_space": f"{freed / 1024 / 1024:.1f} MB",
    }


@tool
def delete_folder(path: str) -> dict:
    """
    Permanently delete a folder AND EVERYTHING INSIDE IT. Requires HITL
    approval. Refuses on protected system paths, the user's home folder, a
    drive root, or a standard alias folder itself (Downloads, Desktop, etc. —
    if the user means "empty out downloads", use search_files + delete_files
    or find_duplicates + delete_all_duplicates on its contents instead).
    """
    import shutil

    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err
    if _is_protected_root(p_obj):
        return {
            "error": (
                f"Refusing to delete the protected top-level folder '{p_obj}'. "
                f"If you mean its contents, search/list it and delete specific "
                f"files instead."
            )
        }

    file_count = sum(1 for f in p_obj.rglob("*") if f.is_file())

    try:
        shutil.rmtree(p_obj)
    except PermissionError:
        return {"error": f"Permission denied deleting {p_obj} (something inside may be open)."}
    except OSError as e:
        return {"error": f"Could not delete {p_obj}: {e}"}

    return {"status": "success", "deleted_path": str(p_obj), "files_removed": file_count}


from tools.memory_tools import write_memory

# Collect all tools
ALL_TOOLS = [
    scan_directory, list_directory, search_files, find_duplicates,
    read_file, read_clipboard, open_file,
    move_file, copy_file, rename_file, create_folder, write_file,
    delete_files, delete_all_duplicates, delete_folder,
    draft_email, write_memory,
]

# Tools that must pass the HITL approval gate before executing.
# draft_email is included because it opens a window pre-filled with the
# user's own data — they approve before anything leaves the machine.
HIGH_RISK_TOOLS = {"delete_files", "delete_all_duplicates", "delete_folder", "draft_email"}
