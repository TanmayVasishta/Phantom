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
import re
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
    """Find duplicate files in a folder by content (byte-for-byte), regardless of name."""
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    duplicates, scan_complete, skipped_folders = _get_duplicates_list(path)

    total_wasted = 0
    paths = []
    for d in duplicates:
        try:
            total_wasted += d.stat().st_size
        except OSError:
            pass
        paths.append(str(d))

    note = (
        f"Scan stopped after {_DUPLICATE_SCAN_BUDGET_SECONDS:.0f}s to stay responsive — "
        f"these subfolders weren't fully checked: {', '.join(skipped_folders[:5])}"
        f"{'…' if len(skipped_folders) > 5 else ''}. Results above are still real "
        f"duplicates, just not necessarily all of them. Ask to scan one of those "
        f"subfolders directly for a complete check of it."
    ) if not scan_complete else None

    if not paths:
        result = {
            "total_duplicates_found": 0,
            "message": f"No duplicate files found in {p_obj}.",
        }
        if note:
            result["incomplete_scan"] = note
        return result

    result = {
        "paths_to_delete_sample": paths[:10],
        "total_duplicates_found": len(paths),
        "wasted_human": f"{total_wasted / 1024 / 1024:.1f} MB",
        "action_required": (
            "To remove these, call delete_all_duplicates(path) — do NOT pass the "
            "list to delete_files, that would blow the token budget."
        ),
    }
    if note:
        result["incomplete_scan"] = note
    return result


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

_COPY_SUFFIX = re.compile(r"(\s*\(\d+\)|[\s_-]+-?\s*copy(\s*\d+)?)$", re.IGNORECASE)
_COPY_PREFIX = re.compile(r"^copy\s+of\s+", re.IGNORECASE)


def _looks_like_copy(stem: str) -> bool:
    """
    Best-effort recognition of common "this is a copy" naming conventions
    — " (1)", " - Copy", " - Copy - Copy", "file copy 2", "Copy of file".

    Used ONLY as a tiebreaker for which file in an already content-confirmed
    duplicate group to keep. Never used to decide whether two files ARE
    duplicates — that decision belongs to _get_duplicates_list's content
    hash alone, since naming conventions vary too much to enumerate (this
    list already needed 4 patterns for ONE Downloads folder) and pattern
    matching alone gets false positives too: "Budget (2024).pdf" would
    wrongly group with "Budget.pdf" under a naming-only check even with
    completely unrelated content.
    """
    return bool(_COPY_SUFFIX.search(stem) or _COPY_PREFIX.match(stem))


_DUPLICATE_SCAN_BUDGET_SECONDS = 10.0  # keeps this comfortably under run_query's 60s timeout


def _get_duplicates_list(path: str) -> tuple[list[Path], bool, list[str]]:
    """
    Find duplicate files by CONTENT, not filename pattern.

    The previous implementation only recognised the Windows "(N)" copy
    suffix (e.g. "report (1).pdf"). Verified live against a real Downloads
    folder: multiple genuine duplicate sets instead used " - Copy" /
    " - Copy - Copy" suffixes (e.g. "23CS7PCMNE.pdf" / "23CS7PCMNE -
    Copy.pdf" / "23CS7PCMNE - Copy - Copy.pdf", all three byte-identical)
    and were silently missed — including a 467MB installer duplicated in
    full. There is no one fixed naming convention: it depends on the OS,
    the browser, and how the copy was made, and pattern-matching also risks
    the opposite mistake (see _looks_like_copy's docstring).

    Content hashing sidesteps both problems: two files are duplicates iff
    their bytes are identical, regardless of what either is named. Files
    are grouped by size first — free, just a stat call — so only files
    that already share a size with something else ever get hashed, and a
    file with no size-twin never touches the disk for this at all.

    Returns (duplicates_to_delete, scan_complete, skipped_folders).
    scan_complete is False only if the RECURSIVE pass below ran out of its
    time budget; direct children of `path` are always fully covered (see
    the two-phase walk below for why).

    Two-phase walk, not one rglob() over everything:
    Measured live on a real Downloads folder: a full recursive scan across
    ~44,000 files (several nested extracted project clones, one of which
    turned out to exist as two full copies) took over three minutes —
    comfortably past run_query()'s 60s timeout. A single time-boxed cutoff
    over one rglob() pass isn't safe either: OS directory enumeration order
    is not reliably alphabetical, so on this exact run a naive 25s cutoff
    would have missed a real 467MB duplicate installer that only got
    reached at the 26.6s mark. Scanning immediate children first (always
    completes — a folder would need an implausible number of DIRECT files
    for this alone to take long) and only THEN recursing into subfolders
    under the time budget guarantees top-level duplicates — what someone
    asking "check my downloads for duplicates" most likely means — are
    never missed, while deeper ones are best-effort and honestly reported
    if the scan had to stop partway.
    """
    import hashlib
    import time
    from collections import defaultdict

    try:
        path_obj = resolve_path(path)
    except ValueError:
        return [], True, []
    if not is_safe_path(path_obj) or not path_obj.exists() or not path_obj.is_dir():
        return [], True, []

    def _bucket(entries) -> dict[int, list[Path]]:
        sizes: dict[int, list[Path]] = defaultdict(list)
        for f in entries:
            try:
                if not f.is_file():
                    continue
                size = f.stat().st_size
            except OSError:
                continue
            if size == 0:
                continue  # empty files aren't meaningfully "duplicates" of each other
            sizes[size].append(f)
        return sizes

    def _partial_hash(fp: Path) -> str | None:
        """First+last 64KB only. Two files that already share a size and
        differ here cannot be equal, so this rules out non-duplicates
        without reading the rest — the deciding cost for a folder like this
        one, which has two 467MB installers as well as several videos: same
        size does not necessarily mean duplicate, and there is no reason to
        read the full file to find that out."""
        h = hashlib.sha256()
        try:
            size = fp.stat().st_size
            with open(fp, "rb") as fh:
                head = fh.read(1 << 16)
                h.update(head)
                if size > len(head):
                    fh.seek(-min(1 << 16, size), os.SEEK_END)
                    h.update(fh.read(1 << 16))
            return h.hexdigest()
        except OSError:
            return None

    def _content_hash(fp: Path) -> str | None:
        h = hashlib.sha256()
        try:
            with open(fp, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def _find_dupes(by_size: dict[int, list[Path]], deadline: float | None) -> tuple[list[Path], bool]:
        """Hash-and-group one size-map. `deadline` is checked once per
        size-group (coarse, not per-file — groups here are typically small,
        so this bounds overshoot to roughly one group's worth of I/O)."""
        found: list[Path] = []
        complete = True
        for size, files in by_size.items():
            if len(files) <= 1:
                continue
            if deadline is not None and time.perf_counter() >= deadline:
                complete = False
                break

            # Cheap pass first: only files that ALSO share a partial hash
            # can possibly be true duplicates, so a full read is skipped
            # for anything already ruled out by its first+last 64KB.
            by_partial: dict[str, list[Path]] = defaultdict(list)
            for f in files:
                p_digest = _partial_hash(f)
                if p_digest is not None:
                    by_partial[p_digest].append(f)

            by_hash: dict[str, list[Path]] = defaultdict(list)
            for candidates in by_partial.values():
                if len(candidates) <= 1:
                    continue
                for f in candidates:
                    digest = _content_hash(f)
                    if digest is not None:
                        by_hash[digest].append(f)

            for group in by_hash.values():
                if len(group) <= 1:
                    continue
                # Keep whichever name doesn't look like a copy (the likely
                # original); ties — including "none of them look like a
                # copy" — fall back to oldest mtime, since the first one
                # created is the most plausible original.
                def _sort_key(f: Path):
                    try:
                        mtime = f.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    return (_looks_like_copy(f.stem), mtime)
                group.sort(key=_sort_key)
                found.extend(group[1:])
        return found, complete

    # Phase 1 — immediate children only, hashed with NO deadline. This is
    # what makes top-level duplicates an architectural guarantee rather
    # than "probably fine in practice": a folder would need an implausible
    # number of same-size DIRECT files for this alone to threaten the
    # budget, and it runs to completion regardless before phase 2 even
    # starts walking anything.
    subdirs: list[Path] = []
    top_level_files: list[Path] = []
    try:
        for entry in path_obj.iterdir():
            try:
                if entry.is_dir():
                    subdirs.append(entry)
                    continue
            except OSError:
                continue
            top_level_files.append(entry)
    except OSError:
        pass

    duplicates_to_delete, _ = _find_dupes(_bucket(top_level_files), deadline=None)

    # Phase 2 — recurse into each subfolder, budgeted for both the walk
    # AND the hashing of whatever it finds (a fast walk doesn't help if
    # hashing its results still blows the budget). A folder is only
    # reported "skipped" if it wasn't fully walked or fully hashed.
    deadline = time.perf_counter() + _DUPLICATE_SCAN_BUDGET_SECONDS
    scan_complete = True
    skipped_folders: list[str] = []
    for sub in subdirs:
        if time.perf_counter() >= deadline:
            scan_complete = False
            skipped_folders.append(sub.name)
            continue

        # Stat inline during the walk (checking the deadline before each
        # file, not after collecting a possibly-huge list) rather than
        # collect-then-_bucket() as a separate pass — collecting first and
        # bucketing after meant a folder with tens of thousands of entries
        # could blow well past the deadline during the "just append to a
        # list" step alone, since nothing bounded how many got collected
        # before the walk noticed time was up.
        by_size_sub: dict[int, list[Path]] = defaultdict(list)
        walked_fully = True
        try:
            for f in sub.rglob("*"):
                if time.perf_counter() >= deadline:
                    walked_fully = False
                    break
                try:
                    if not f.is_file():
                        continue
                    size = f.stat().st_size
                except OSError:
                    continue
                if size:  # empty files aren't meaningfully "duplicates"
                    by_size_sub[size].append(f)
        except OSError:
            pass

        deep_dupes, hashed_fully = _find_dupes(by_size_sub, deadline=deadline)
        duplicates_to_delete.extend(deep_dupes)
        if not (walked_fully and hashed_fully):
            scan_complete = False
            skipped_folders.append(sub.name)

    return duplicates_to_delete, scan_complete, skipped_folders


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
    Delete all content-duplicate files in a folder (byte-identical to
    another file present, regardless of naming), keeping one original per
    group. Requires HITL approval.
    """
    try:
        p_obj = resolve_path(path)
    except ValueError as e:
        return {"error": str(e)}

    err = _guard(p_obj, expect="dir")
    if err:
        return err

    duplicates, scan_complete, skipped_folders = _get_duplicates_list(path)
    if not duplicates:
        result = {"message": f"No duplicates found in {p_obj}.", "deleted_count": 0}
        if not scan_complete:
            result["incomplete_scan"] = (
                f"Scan stopped after {_DUPLICATE_SCAN_BUDGET_SECONDS:.0f}s — "
                f"not fully checked: {', '.join(skipped_folders[:5])}"
            )
        return result

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

    result = {
        "deleted_count": len(deleted),
        "deleted_sample": deleted[:10],
        "failed_count": len(failed),
        "failed": failed[:5],
        "freed_space": f"{freed / 1024 / 1024:.1f} MB",
    }
    if not scan_complete:
        result["incomplete_scan"] = (
            f"Scan stopped after {_DUPLICATE_SCAN_BUDGET_SECONDS:.0f}s — these "
            f"subfolders weren't fully checked and may still contain duplicates: "
            f"{', '.join(skipped_folders[:5])}{'…' if len(skipped_folders) > 5 else ''}"
        )
    return result


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
