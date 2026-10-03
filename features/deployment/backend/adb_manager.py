"""Wireless ADB and USB multi-device manager for instant 1-click APK installation.

Discovers connected Android devices over Wi-Fi and USB, connects wireless ADB targets,
and pushes APKs in parallel to all QA desk devices. Python standard library only.
"""

from __future__ import annotations

import concurrent.futures
import logging
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Optional


def find_adb_binary() -> Optional[str]:
    """Locate the adb binary in PATH or Android SDK platform-tools."""
    # 1. System PATH
    found = shutil.which("adb")
    if found:
        return found

    # 2. Environment variables
    for env_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(env_var, "").strip()
        if val:
            cand = Path(val) / "platform-tools" / "adb"
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand.resolve())

    # 3. Common locations
    home = Path.home()
    common_cands = [
        home / "Android" / "Sdk" / "platform-tools" / "adb",
        home / "Library" / "Android" / "sdk" / "platform-tools" / "adb",
        Path("/usr/bin/adb"),
        Path("/usr/local/bin/adb"),
        Path("/opt/android-sdk/platform-tools/adb"),
    ]
    for cand in common_cands:
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand.resolve())

    return None


def get_adb_devices(adb_path: Optional[str] = None) -> dict[str, Any]:
    """List connected Android devices with detailed metadata (USB, Wi-Fi, Model, Status)."""
    exe = adb_path or find_adb_binary()
    if not exe:
        return {
            "success": True,
            "adbAvailable": False,
            "adbPath": None,
            "devices": [],
            "count": 0,
            "message": "ADB binary not found. Please install Android Platform Tools.",
        }

    try:
        proc = subprocess.run(
            [exe, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception as exc:
        logging.warning("Failed to execute adb devices: %s", exc)
        return {
            "success": False,
            "adbAvailable": True,
            "adbPath": exe,
            "devices": [],
            "count": 0,
            "error": str(exc),
        }

    devices: list[dict[str, Any]] = []
    lines = proc.stdout.splitlines()

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        status = parts[1]

        # Extract key:value properties like model:Pixel_6, product:..., transport_id:...
        props: dict[str, str] = {}
        for token in parts[2:]:
            if ":" in token:
                k, v = token.split(":", 1)
                props[k] = v

        model = props.get("model") or props.get("device") or serial
        # Clean model underscores for better UX (e.g. Pixel_7 -> Pixel 7)
        friendly_model = model.replace("_", " ")

        conn_type = "usb"
        if ":" in serial:
            conn_type = "wifi"
        elif serial.startswith("emulator-"):
            conn_type = "emulator"

        devices.append({
            "serial": serial,
            "status": status,
            "type": conn_type,
            "model": friendly_model,
            "rawModel": model,
            "product": props.get("product", ""),
            "transportId": props.get("transport_id", ""),
            "isReady": status == "device",
        })

    return {
        "success": True,
        "adbAvailable": True,
        "adbPath": exe,
        "devices": devices,
        "count": len(devices),
    }


def connect_wireless_adb(address: str, adb_path: Optional[str] = None) -> dict[str, Any]:
    """Connect to a wireless ADB target (e.g. 192.168.1.50:5555)."""
    exe = adb_path or find_adb_binary()
    if not exe:
        return {"success": False, "error": "ADB binary not found."}

    address = address.strip()
    if not address:
        return {"success": False, "error": "Address is required."}

    if ":" not in address:
        address = f"{address}:5555"

    try:
        proc = subprocess.run(
            [exe, "connect", address],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        out = (proc.stdout + " " + proc.stderr).strip()
        success = "connected to" in out.lower() or "already connected" in out.lower()
        return {
            "success": success,
            "address": address,
            "output": out,
            "error": None if success else out,
        }
    except Exception as exc:
        return {"success": False, "address": address, "error": str(exc)}


def disconnect_wireless_adb(address: str, adb_path: Optional[str] = None) -> dict[str, Any]:
    """Disconnect a wireless ADB target."""
    exe = adb_path or find_adb_binary()
    if not exe:
        return {"success": False, "error": "ADB binary not found."}

    try:
        proc = subprocess.run(
            [exe, "disconnect", address.strip()],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return {"success": True, "output": (proc.stdout + " " + proc.stderr).strip()}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _install_apk_single_device(
    adb_exe: str,
    serial: str,
    apk_path: str,
    model: str = "",
    conn_type: str = "usb",
) -> dict[str, Any]:
    """Install APK to a single device and record timing."""
    start_time = time.time()
    try:
        proc = subprocess.run(
            [adb_exe, "-s", serial, "install", "-r", "-d", str(apk_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        duration = round(time.time() - start_time, 2)
        out = (proc.stdout + " " + proc.stderr).strip()
        success = proc.returncode == 0 and "Success" in out

        return {
            "serial": serial,
            "model": model or serial,
            "type": conn_type,
            "status": "success" if success else "failed",
            "durationSeconds": duration,
            "output": out if out else ("Success" if success else "Unknown error"),
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        duration = round(time.time() - start_time, 2)
        return {
            "serial": serial,
            "model": model or serial,
            "type": conn_type,
            "status": "failed",
            "durationSeconds": duration,
            "output": "Installation timed out after 120 seconds.",
            "returncode": -1,
        }
    except Exception as exc:
        duration = round(time.time() - start_time, 2)
        return {
            "serial": serial,
            "model": model or serial,
            "type": conn_type,
            "status": "failed",
            "durationSeconds": duration,
            "output": str(exc),
            "returncode": -1,
        }


def push_apk_to_devices(
    target: str,
    device_serials: Optional[list[str]] = None,
    adb_path: Optional[str] = None,
) -> dict[str, Any]:
    """Push APK in parallel to selected or all connected ready Android devices."""
    from artifacts.scanner import resolve_safe_apk_path
    from artifacts.network import format_bytes

    exe = adb_path or find_adb_binary()
    if not exe:
        return {"success": False, "error": "ADB binary not found."}

    # Resolve safe APK path
    apk_file: Optional[Path] = None
    cand = Path(target)
    if cand.is_file() and cand.suffix.lower() == ".apk":
        apk_file = cand.resolve()
    else:
        apk_file = resolve_safe_apk_path(target)

    if not apk_file or not apk_file.is_file():
        return {
            "success": False,
            "error": f"APK not found for target '{target}'. Please build the APK first.",
        }

    # Query connected devices
    dev_info = get_adb_devices(adb_path=exe)
    ready_devices = [d for d in dev_info.get("devices", []) if d.get("isReady")]

    if not ready_devices:
        return {
            "success": False,
            "error": "No ready Android devices found. Check USB connection or run Wireless ADB connect.",
        }

    # Filter target devices if requested
    target_devices = ready_devices
    if device_serials:
        target_serials_set = set(device_serials)
        target_devices = [d for d in ready_devices if d["serial"] in target_serials_set]

    if not target_devices:
        return {
            "success": False,
            "error": "None of the specified devices are connected and authorized.",
        }

    results: list[dict[str, Any]] = []
    # Execute installations in parallel across all devices
    max_workers = min(len(target_devices), 8)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _install_apk_single_device,
                exe,
                d["serial"],
                str(apk_file),
                d.get("model", ""),
                d.get("type", "usb"),
            ): d
            for d in target_devices
        }
        for future in concurrent.futures.as_completed(future_map):
            results.append(future.result())

    # Sort results by serial for deterministic response
    results.sort(key=lambda r: r.get("serial", ""))

    success_count = sum(1 for r in results if r.get("status") == "success")
    file_stat = apk_file.stat()

    return {
        "success": True,
        "apkPath": str(apk_file),
        "filename": apk_file.name,
        "sizeFormatted": format_bytes(file_stat.st_size),
        "totalDevices": len(results),
        "successCount": success_count,
        "failedCount": len(results) - success_count,
        "results": results,
    }
