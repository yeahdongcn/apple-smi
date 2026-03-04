"""Process listing for GPU usage on macOS."""

import os
import re
import subprocess
from dataclasses import dataclass

# Known graphics/system processes (UI, compositors, renderers, etc.)
_GRAPHICS_PATTERNS = {
    "WindowServer", "Dock", "Finder", "loginwindow", "ControlCenter",
    "ControlStrip", "NotificationCenter", "Spotlight", "TouchBarServer",
    "SystemUIServer", "DockHelper", "AccessibilityVisuals", "replayd",
    "NeptuneOneWallpaper", "CursorUIViewService", "TextInputMenuAgent",
    "TextInputSwitcher", "NowPlayingTouchUI", "ThemeWidgetContent",
    "AutoFillPanelService", "avconferenced", "iconservicesagent",
    "LocalAuthentication", "runningboardd", "iPhone Mirroring",
    "QuickLookUIService", "DisplayLinkUserAgent", "BetterDisplay",
    "Hidden Bar", "Input Source Pro", "ViewBridgeAuxiliary",
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


def _classify_process(name: str, full_cmd: str) -> str:
    """Classify a process as G (Graphics) or C (Compute)."""
    # Check if it's a known graphics process (case-insensitive)
    name_u = name.upper()
    for pattern in _GRAPHICS_PATTERNS:
        if name_u == pattern.upper() or pattern.upper() in name_u:
            return "G"

    # Check if it's a known compute process
    check = (name + " " + full_cmd).lower()
    for pattern in _COMPUTE_PATTERNS:
        if pattern.lower() in check:
            return "C"

    # Default for unidentified system processes from common paths
    if "/System/Library/" in full_cmd or "/usr/libexec/" in full_cmd:
        return "G"

    return "G"


def get_gpu_processes(show_all: bool = False) -> list[ProcessInfo]:
    """Get list of processes using the GPU."""
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

    # Get PIDs of processes using the GPU
    # Regex find: "IOUserClientCreator" = "pid 636, WindowServer"
    pattern = re.compile(r'"IOUserClientCreator"\s*=\s*"pid\s+(\d+),')
    pids = set()
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            pids.add(int(match.group(1)))

    if not pids:
        return []

    # Get detailed info via ps (pid, rss, command)
    # Using 'command' avoids the 16-character 'comm' limit and prevents splitting ambiguity.
    processes = []
    try:
        pid_list = ",".join(map(str, pids))
        ps_result = subprocess.run(
            ["ps", "-o", "pid,rss,command", "-p", pid_list],
            capture_output=True,
            text=True,
        )

        lines = ps_result.stdout.strip().splitlines()
        if len(lines) > 1:
            for line in lines[1:]:
                # Split only for PID and RSS, everything else is the command string
                parts = line.split(None, 2)
                if len(parts) >= 3:
                    pid = int(parts[0])
                    rss_kb = int(parts[1])
                    full_cmd = parts[2].strip()
                    
                    # 1. Default name: first word of the command
                    cmd_parts = full_cmd.split()
                    raw_bin = cmd_parts[0]
                    name = os.path.basename(raw_bin) if "/" in raw_bin else raw_bin

                    # 2. Robust path matching: handle spaces in absolute paths (e.g. /Applications/My App/...)
                    if full_cmd.startswith("/"):
                        temp_path = ""
                        for part in cmd_parts:
                            temp_path = (temp_path + " " + part).strip()
                            if os.path.isfile(temp_path):
                                name = os.path.basename(temp_path)
                                break

                    # 3. Special case: Python scripts
                    if name.lower().startswith("python") and len(cmd_parts) > 1:
                        script = cmd_parts[1]
                        if not script.startswith("-"):
                            name = os.path.basename(script)
                    
                    mem_bytes = rss_kb * 1024
                    proc_type = _classify_process(name, full_cmd)

                    processes.append(ProcessInfo(
                        pid=pid,
                        name=name,
                        type=proc_type,
                        memory_usage_bytes=mem_bytes,
                    ))
    except Exception:
        pass

    # Filter by type unless show_all
    if not show_all:
        processes = [p for p in processes if p.type == "C"]

    # Sort by memory usage descending
    processes.sort(key=lambda x: x.memory_usage_bytes, reverse=True)

    return processes

    # Filter by type unless show_all
    if not show_all:
        processes = [p for p in processes if p.type == "C"]

    # Sort by memory usage descending
    processes.sort(key=lambda x: x.memory_usage_bytes, reverse=True)

    return processes
