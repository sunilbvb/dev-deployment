"""Native folder/file dialogs, opened by the local server on the user's own desktop.

Browsers never reveal absolute paths, but the console server runs on the same
machine, so it can show the OS picker and return the real path.
"""
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

PICK_TIMEOUT_SECONDS = 600

# Folders the user chose in a native dialog during this server session. Choosing a
# folder is an explicit grant, so it may be inspected even outside authorised roots.
_PICKED_PATHS: set[str] = set()


def was_picked(path: Path) -> bool:
    return str(path.resolve()) in _PICKED_PATHS


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _mac_command(kind: str, prompt: str, start: str, extensions: list[str]) -> list[str]:
    parts = [f"choose {'folder' if kind == 'folder' else 'file'} with prompt {_applescript_string(prompt)}"]
    if start and Path(start).is_dir():
        parts.append(f"default location POSIX file {_applescript_string(start)}")
    if kind == "file" and extensions:
        parts.append("of type {" + ", ".join(_applescript_string(e) for e in extensions) + "}")
    script = f"POSIX path of ({' '.join(parts)})"
    return ["osascript", "-e", script]


def _linux_command(kind: str, prompt: str, start: str, extensions: list[str]) -> list[str]:
    cmd = ["zenity", "--file-selection", f"--title={prompt}"]
    if kind == "folder":
        cmd.append("--directory")
    if start and Path(start).is_dir():
        cmd.append(f"--filename={start.rstrip('/')}/")
    if kind == "file" and extensions:
        cmd.append("--file-filter=" + " ".join(f"*.{e}" for e in extensions))
    return cmd


def pick_path(kind: str = "folder", prompt: str = "", start: str = "", extensions: Any = None) -> dict[str, Any]:
    if kind not in ("folder", "file"):
        return {"success": False, "error": "kind must be 'folder' or 'file'"}
    prompt = (prompt or ("Choose a folder" if kind == "folder" else "Choose a file"))[:200]
    exts = [str(e).lstrip(".")[:10] for e in (extensions or []) if str(e).strip()][:10]
    start = str(Path(start).expanduser()) if start else ""

    system = platform.system()
    if system == "Darwin" and shutil.which("osascript"):
        cmd = _mac_command(kind, prompt, start, exts)
    elif system == "Linux" and shutil.which("zenity"):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return {
                "success": False,
                "supported": False,
                "error": "No GUI display detected on Linux server; type the folder path instead.",
            }
        cmd = _linux_command(kind, prompt, start, exts)
    else:
        return {"success": False, "supported": False,
                "error": "No native file dialog available on this system; type the path instead."}

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PICK_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"success": False, "cancelled": True, "error": "The dialog was left open too long"}
    except Exception as e:
        return {"success": False, "supported": False, "error": f"Failed to run dialog: {e}"}

    if proc.returncode != 0:
        # osascript exits 1 with "User canceled" (-128); zenity exits 1 on cancel.
        err = (proc.stderr or "").strip()
        if err and "cancel" not in err.lower():
            return {"success": False, "cancelled": True, "error": err}
        return {"success": False, "cancelled": True}
    chosen = proc.stdout.strip()
    if not chosen:
        return {"success": False, "cancelled": True}
    path = str(Path(chosen).expanduser().resolve())
    _PICKED_PATHS.add(path)
    return {"success": True, "supported": True, "path": path}
