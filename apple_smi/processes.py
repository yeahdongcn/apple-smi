"""Process listing for GPU usage on macOS."""

import os
import re
import subprocess
from dataclasses import dataclass

# Known graphics/system processes (UI, compositors, renderers, etc.)
_GRAPHICS_PATTERNS = {
    "WindowServer", "Dock", "Finder", "loginwindow", "ControlCenter",
    "ControlStrip", "NotificationCent", "Spotlight", "TouchBarServer",
    "SystemUIServer", "DockHelper", "AccessibilityUIS", "replayd",
    "NeptuneOneWallpa", "CursorUIViewServ", "TextInputMenuAge",
    "TextInputSwitche", "NowPlayingTouchU", "ThemeWidgetContr",
    "AutoFillPanelSer", "avconferenced", "iconservicesagen",
    "LocalAuthenticat", "runningboardd", "iPhone Mirroring",
    "QuickLookUIServi", "DisplayLinkUserA", "BetterDisplay",
    "Hidden Bar", "Input Source Pro",
}

# Known compute process patterns (ML/AI frameworks, scientific computing, etc.)
_COMPUTE_PATTERNS = [
    "python", "Python", "mlx", "tensorflow", "torch", "jax",
    "ollama", "lmstudio", "stable-diffusion", "comfyui",
    "whisper", "llama", "vllm", "sglang", "triton",
    "blender", "resolve", "fcpx", "compressor",
    "Metal", "metalcompute",
]


@dataclass
class ProcessInfo:
    """Information about a process using the GPU."""

    pid: int
    name: str
    type: str = "G"  # G for Graphics, C for Compute
    memory_usage_bytes: int = 0


def _classify_process(name: str, comm: str) -> str:
    """Classify a process as G (Graphics) or C (Compute).

    Graphics processes are known system UI processes.
    Compute processes are ML/AI/rendering apps.
    Default is G for unrecognized processes.
    """
    # Check if it's a known graphics process
    for pattern in _GRAPHICS_PATTERNS:
        if name.startswith(pattern) or pattern in name:
            return "G"

    # Check if it's a known compute process (by name or full command)
    check = (name + " " + comm).lower()
    for pattern in _COMPUTE_PATTERNS:
        if pattern.lower() in check:
            return "C"

    # Default: Graphics (most GPU-using processes on macOS are graphical)
    return "G"


def get_gpu_processes(show_all: bool = False) -> list[ProcessInfo]:
    """Get list of processes using the GPU by parsing ioreg.

    Args:
        show_all: If True, return all GPU processes (G + C).
                  If False, return only Compute (C) processes.
    """
    try:
        # ioreg lists user clients of the accelerator
        result = subprocess.run(
            ["ioreg", "-c", "IOAccelerator", "-r", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout
    except Exception:
        return []

    # Regex to find "IOUserClientCreator" = "pid 636, WindowServer"
    pattern = re.compile(r'"IOUserClientCreator"\s*=\s*"pid\s+(\d+),\s+(.*?)"')

    pids_found = {}  # pid -> name
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            pid = int(match.group(1))
            name = match.group(2).strip()
            pids_found[pid] = name

    if not pids_found:
        return []

    # Get additional info (memory, full command) via ps
    processes = []
    try:
        pid_list = ",".join(map(str, pids_found.keys()))
        ps_result = subprocess.run(
            ["ps", "-o", "pid,rss,comm", "-p", pid_list],
            capture_output=True,
            text=True,
        )

        lines = ps_result.stdout.strip().splitlines()
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split(None, 2)
                if len(parts) >= 2:
                    pid = int(parts[0])
                    rss_kb = int(parts[1])
                    comm = parts[2] if len(parts) > 2 else ""
                    mem_bytes = rss_kb * 1024

                    name = pids_found.get(pid, "Unknown")
                    proc_type = _classify_process(name, comm)

                    processes.append(ProcessInfo(
                        pid=pid,
                        name=name,
                        type=proc_type,
                        memory_usage_bytes=mem_bytes,
                    ))
    except Exception:
        for pid, name in pids_found.items():
            proc_type = _classify_process(name, "")
            processes.append(ProcessInfo(pid=pid, name=name, type=proc_type))

    # Filter by type unless show_all
    if not show_all:
        processes = [p for p in processes if p.type == "C"]

    # Sort by memory usage descending
    processes.sort(key=lambda x: x.memory_usage_bytes, reverse=True)

    return processes
