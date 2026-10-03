"""Build Time Profiler & Compilation Bottleneck Heatmap.

Parses Gradle, Xcode, and Flutter build logs to compute compile timings,
phase breakdowns (Dependencies, Compilation, Assets, Linking, Packaging, Signing),
and flags compilation bottlenecks with actionable tuning recommendations.
Python standard library only.
"""

from __future__ import annotations

import re
from typing import Any, Optional

PHASE_DEFS = [
    {
        "id": "dependencies",
        "name": "Dependencies & Pre-flight",
        "color": "#6366f1",  # Indigo
        "patterns": [
            r":preBuild",
            r":resolveDependencies",
            r"flutter pub get",
            r"Resolving dependencies",
            r"Running \"flutter pub get\"",
            r"pod install",
            r"Analyzing dependencies",
            r"Resolve Package Graph",
            r":check\w*AarMetadata",
        ],
        "tip": "Prime dependencies in background using the Silent Cache Warmer to eliminate pre-flight lag.",
    },
    {
        "id": "compilation",
        "name": "Code Compilation",
        "color": "#f59e0b",  # Amber
        "patterns": [
            r"compileFlutterBuild",
            r"compile\w*Kotlin",
            r"compile\w*JavaWithJavac",
            r"CompileSwiftSources",
            r"CompileC",
            r"swiftc",
            r"bundle\w*JsAndAssets",
            r"hermes",
            r"Building bundle",
            r"Building AOT snapshot",
        ],
        "tip": "Enable Gradle build cache (`org.gradle.caching=true`) and Kotlin daemon incremental compilation.",
    },
    {
        "id": "assets",
        "name": "Asset & Resource Processing",
        "color": "#10b981",  # Emerald
        "patterns": [
            r"process\w*Resources",
            r"merge\w*Resources",
            r"aapt2",
            r"CompileAssetCatalog",
            r"actool",
            r"flutter_assets",
            r"compressXml",
        ],
        "tip": "Optimize and convert raw PNG assets to WebP or vector drawables to reduce AAPT2/actool overhead.",
    },
    {
        "id": "linking",
        "name": "Native Libs & Linking",
        "color": "#38bdf8",  # Sky Blue
        "patterns": [
            r"merge\w*NativeLibs",
            r"strip\w*DebugSymbols",
            r"Ld\s",
            r"libtool",
            r"link\w*",
        ],
        "tip": "Configure `ndk.abiFilters` in build.gradle to compile only required device architectures.",
    },
    {
        "id": "packaging",
        "name": "Packaging & Bundling",
        "color": "#ec4899",  # Pink
        "patterns": [
            r"package\w*",
            r"bundle\w*Release",
            r"bundle\w*Debug",
            r"ExportArchive",
            r"assemble\w*",
            r"create\w*ApkListing",
        ],
        "tip": "Use parallel compression and keep unneeded test files out of packaging directories.",
    },
    {
        "id": "signing",
        "name": "Code Signing & Verification",
        "color": "#8b5cf6",  # Purple
        "patterns": [
            r"validateSigning\w*",
            r"sign\w*Bundle",
            r"zipalign",
            r"apksigner",
            r"CodeSign",
            r"codesign",
        ],
        "tip": "Ensure signing certificates and provisioning profiles are cached locally to avoid keychain delays.",
    },
]

# Regex to match Gradle task duration: e.g. "> Task :app:compileFlutterBuildDebug (12.5s)" or "(250ms)"
GRADLE_TASK_REGEX = re.compile(
    r">\s*Task\s+(:[a-zA-Z0-9_:]+)\s*(?:UP-TO-DATE|FROM-CACHE|\(([0-9.]+)(m?s)\))?",
    re.IGNORECASE,
)

# Regex to match terminal log timestamps: "12:34:56  ..."
TIMESTAMP_LINE_REGEX = re.compile(r"^(\d{2}):(\d{2}):(\d{2})\s+(.*)$")


def parse_gradle_task_timings(log_text: str) -> dict[str, float]:
    """Extract individual Gradle task execution durations in seconds from build logs."""
    task_timings: dict[str, float] = {}
    for line in log_text.splitlines():
        match = GRADLE_TASK_REGEX.search(line)
        if match:
            task_name = match.group(1)
            duration_val = match.group(2)
            unit = match.group(3)
            if duration_val:
                sec = float(duration_val)
                if unit == "ms":
                    sec /= 1000.0
                task_timings[task_name] = round(sec, 2)
    return task_timings


def profile_build_log(
    log_text: str,
    command: str = "",
    total_duration_sec: Optional[float] = None,
) -> dict[str, Any]:
    """Profile build log into compilation phases and isolate bottlenecks."""
    if not log_text:
        log_text = ""

    phase_times: dict[str, float] = {p["id"]: 0.0 for p in PHASE_DEFS}
    phase_times["other"] = 0.0

    task_timings = parse_gradle_task_timings(log_text)

    # 1. Attribute Gradle task timings if present
    if task_timings:
        for task_name, sec in task_timings.items():
            matched_phase = False
            for pdef in PHASE_DEFS:
                for pat in pdef["patterns"]:
                    if re.search(pat, task_name, re.IGNORECASE):
                        phase_times[pdef["id"]] += sec
                        matched_phase = True
                        break
                if matched_phase:
                    break
            if not matched_phase:
                phase_times["other"] += sec

    # 2. If no explicit Gradle timings found or total is low, attribute by line frequency & timestamps
    sum_attributed = sum(phase_times.values())
    lines = log_text.splitlines()

    if sum_attributed < 1.0 and lines:
        # Match lines with phase patterns
        line_counts: dict[str, int] = {p["id"]: 0 for p in PHASE_DEFS}
        for line in lines:
            for pdef in PHASE_DEFS:
                for pat in pdef["patterns"]:
                    if re.search(pat, line, re.IGNORECASE):
                        line_counts[pdef["id"]] += 1
                        break

        total_matches = sum(line_counts.values())
        effective_total = total_duration_sec if (total_duration_sec and total_duration_sec > 0) else 10.0

        if total_matches > 0:
            for pid, cnt in line_counts.items():
                phase_times[pid] = round((cnt / total_matches) * (effective_total * 0.85), 2)
            phase_times["other"] = round(effective_total * 0.15, 2)
        else:
            # Fallback heuristic distribution based on standard mobile builds
            phase_times["dependencies"] = round(effective_total * 0.10, 2)
            phase_times["compilation"] = round(effective_total * 0.50, 2)
            phase_times["assets"] = round(effective_total * 0.15, 2)
            phase_times["linking"] = round(effective_total * 0.08, 2)
            phase_times["packaging"] = round(effective_total * 0.10, 2)
            phase_times["signing"] = round(effective_total * 0.07, 2)
            phase_times["other"] = 0.0

    # Ensure total duration matches or exceeds sum
    computed_sum = sum(phase_times.values())
    total_sec = total_duration_sec if (total_duration_sec and total_duration_sec >= computed_sum) else computed_sum
    if total_sec <= 0:
        total_sec = 1.0

    # If there's unallocated time, put it into other
    if total_sec > computed_sum:
        phase_times["other"] = round(phase_times["other"] + (total_sec - computed_sum), 2)

    # Format output phases
    phases_out: list[dict[str, Any]] = []
    bottlenecks: list[dict[str, Any]] = []

    for pdef in PHASE_DEFS:
        pid = pdef["id"]
        sec = round(phase_times.get(pid, 0.0), 2)
        pct = round((sec / total_sec) * 100.0, 1)
        phases_out.append({
            "id": pid,
            "name": pdef["name"],
            "color": pdef["color"],
            "durationSeconds": sec,
            "percentage": pct,
            "tip": pdef["tip"],
        })
        if pct >= 30.0:
            severity = "critical" if pct >= 50.0 else "high"
            bottlenecks.append({
                "phaseId": pid,
                "phaseName": pdef["name"],
                "percentage": pct,
                "durationSeconds": sec,
                "severity": severity,
                "tip": pdef["tip"],
            })

    # Add other / system overhead if non-zero
    other_sec = round(phase_times.get("other", 0.0), 2)
    other_pct = round((other_sec / total_sec) * 100.0, 1)
    if other_sec > 0:
        phases_out.append({
            "id": "other",
            "name": "System & I/O Overhead",
            "color": "#64748b",  # Slate
            "durationSeconds": other_sec,
            "percentage": other_pct,
            "tip": "General OS I/O and process spawn overhead.",
        })

    # Sort bottlenecks descending by percentage
    bottlenecks.sort(key=lambda b: b["percentage"], reverse=True)

    summary = "Build timings distributed evenly across phases."
    if bottlenecks:
        primary = bottlenecks[0]
        summary = f"{primary['phaseName']} was the primary bottleneck ({primary['percentage']}% of build time)."

    return {
        "success": True,
        "totalDurationSeconds": round(total_sec, 2),
        "phases": phases_out,
        "bottlenecks": bottlenecks,
        "summary": summary,
        "hasBottlenecks": len(bottlenecks) > 0,
    }


def get_job_build_profile(job_id: Optional[str] = None) -> dict[str, Any]:
    """Retrieve and profile build timings for a specific job ID or the latest job."""
    import jobs

    job_info = None
    if job_id:
        job_info = jobs.get_job(job_id).get("job")
    if not job_info:
        # Fall back to latest job in history
        history = jobs.get_deployment_history(limit=1).get("history", [])
        if history:
            job_info = history[0]

    if not job_info:
        return {
            "success": False,
            "error": "No deployment job found to profile.",
        }

    raw_output = (job_info.get("output") or "") + "\n" + (job_info.get("error") or "")
    started = job_info.get("started_at")
    finished = job_info.get("finished_at")
    duration = None
    if started and finished:
        duration = finished - started

    profile_data = profile_build_log(
        log_text=raw_output,
        command=job_info.get("command", ""),
        total_duration_sec=duration,
    )
    profile_data["jobId"] = job_info.get("id")
    profile_data["app"] = job_info.get("app")
    profile_data["flavor"] = job_info.get("flavor") or job_info.get("env")
    profile_data["command"] = job_info.get("command")
    profile_data["status"] = job_info.get("status")

    return profile_data
