"""SoC information from sysctl, sw_vers, and IORegistry (Fast)."""

import os
import re
import subprocess
from dataclasses import dataclass, field

from .iokit import get_gpu_freq_table

# Estimated TDP for Apple Silicon chips (Watts)
_TDP_TABLE: dict[str, float] = {
    "Apple M1": 20,
    "Apple M1 Pro": 30,
    "Apple M1 Max": 60,
    "Apple M1 Ultra": 120,
    "Apple M2": 22,
    "Apple M2 Pro": 30,
    "Apple M2 Max": 60,
    "Apple M2 Ultra": 120,
    "Apple M3": 22,
    "Apple M3 Pro": 36,
    "Apple M3 Max": 75,
    "Apple M3 Ultra": 150,
    "Apple M4": 22,
    "Apple M4 Pro": 40,
    "Apple M4 Max": 75,
    "Apple M4 Ultra": 150,
    "Apple M5": 22,
    "Apple M5 Pro": 40,
    "Apple M5 Max": 75,
    "Apple M5 Ultra": 150,
}


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
    tdp_w: float = 0.0  # Estimated TDP in Watts


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

    # Guess Metal version based on chip family
    if "M4" in info.chip_name:
        info.metal_family = "4"
    else:
        info.metal_family = "3"  # M1, M2, M3 all support Metal 3 on modern macOS

    # ── TDP estimation ────────────────────────────────────────────────────
    info.tdp_w = _TDP_TABLE.get(info.chip_name, 0.0)
    if info.tdp_w == 0.0:
        for chip, tdp in _TDP_TABLE.items():
            if info.chip_name.startswith(chip):
                info.tdp_w = tdp
                break

    # ── GPU frequency table (IORegistry) ───────────────────────────────
    info.gpu_freqs_mhz = get_gpu_freq_table()

    return info
