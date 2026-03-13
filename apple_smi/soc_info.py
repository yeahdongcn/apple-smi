"""SoC information from sysctl, sw_vers, and IORegistry (Fast)."""

import os
import re
import subprocess
from dataclasses import dataclass, field

from .iokit import get_gpu_freq_table

@dataclass
class SocInfo:
    """Static information about the Apple Silicon SoC."""

    chip_name: str = "Unknown"
    mac_model: str = "Unknown"
    memory_gb: int = 0
    ecpu_cores: int = 0
    pcpu_cores: int = 0
    gpu_cores: int = 0
    gpu_freqs_mhz: list[int] = field(default_factory=list)
    metal_family: str = "Metal"
    os_version: str = "macOS"



def _run_cmd(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def get_soc_info() -> SocInfo:
    """Gather SoC information using fast targeted system commands."""
    info = SocInfo()

    # ── CPU & Model info via sysctl (Single call) ────────────────────────
    # hw.model: Model identifier
    # machdep.cpu.brand_string: Full chip name
    # hw.memsize: RAM in bytes
    # hw.perflevel0.physicalcpu: P-cores
    # hw.perflevel1.physicalcpu: E-cores
    sysctl_data = _run_cmd([
        "sysctl", "-n",
        "hw.model",
        "machdep.cpu.brand_string",
        "hw.memsize",
        "hw.perflevel0.physicalcpu",
        "hw.perflevel1.physicalcpu"
    ]).splitlines()

    if len(sysctl_data) >= 3:
        info.mac_model = sysctl_data[0]
        info.chip_name = sysctl_data[1]
        try:
            info.memory_gb = int(sysctl_data[2]) // (1024**3)
        except Exception:
            pass

    if len(sysctl_data) >= 5:
        try:
            info.pcpu_cores = int(sysctl_data[3])
            info.ecpu_cores = int(sysctl_data[4])
        except Exception:
            pass

    # ── OS Version via sw_vers (Fast) ────────────────────────────────────
    ver = _run_cmd(["sw_vers", "-productVersion"])
    build = _run_cmd(["sw_vers", "-buildVersion"])
    if ver:
        info.os_version = f"{ver} ({build})" if build else ver

    # ── GPU count via targeted ioreg ─────────────────────────────────────
    gpu_cores_data = _run_cmd(["ioreg", "-k", "gpu-core-count", "-r", "-l", "-d", "1"])
    match_cores = re.search(r'"gpu-core-count"\s*=\s*(\d+)', gpu_cores_data)
    if match_cores:
        info.gpu_cores = int(match_cores.group(1))

    # Dynamic Metal version detection (Fast with -detailLevel mini)
    metal_data = _run_cmd(["system_profiler", "SPDisplaysDataType", "-detailLevel", "mini"])
    match_metal = re.search(r"Metal Support:\s*Metal\s*(\d+)", metal_data)
    if match_metal:
        info.metal_family = match_metal.group(1)
    else:
        # Fallback guess based on chip family
        if any(x in info.chip_name for x in ["M4", "M5"]):
            info.metal_family = "4"
        else:
            info.metal_family = "3"  # Default for original M1/M2/M3

    # ── GPU frequency table (IORegistry) ───────────────────────────────
    info.gpu_freqs_mhz = get_gpu_freq_table()

    return info
