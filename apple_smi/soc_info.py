"""SoC information from system_profiler and IORegistry."""

import json
import subprocess
from dataclasses import dataclass, field

from .iokit import get_gpu_freq_table

# Estimated TDP for Apple Silicon chips (Watts)
# These are approximate values based on teardown/benchmark analyses
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


def get_soc_info() -> SocInfo:
    """Gather SoC information from system_profiler and IORegistry."""
    info = SocInfo()

    # ── system_profiler ───────────────────────────────────────────────────
    try:
        result = subprocess.run(
            [
                "system_profiler",
                "SPHardwareDataType",
                "SPDisplaysDataType",
                "SPSoftwareDataType",
                "-json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
    except Exception:
        data = {}

    # Hardware info
    hw = data.get("SPHardwareDataType", [{}])[0] if data.get("SPHardwareDataType") else {}
    info.chip_name = hw.get("chip_type", "Unknown")
    info.mac_model = hw.get("machine_model", "Unknown")

    # Memory: "x GB" string
    mem_str = hw.get("physical_memory", "0 GB")
    try:
        info.memory_gb = int(mem_str.replace(" GB", ""))
    except ValueError:
        info.memory_gb = 0

    # CPU cores: "proc x:y:z" string (total:pcpu:ecpu)
    cores_str = hw.get("number_processors", "")
    if cores_str.startswith("proc "):
        parts = cores_str[5:].split(":")
        if len(parts) == 3:
            try:
                info.pcpu_cores = int(parts[1])
                info.ecpu_cores = int(parts[2])
            except ValueError:
                pass

    # Display / GPU info
    displays = data.get("SPDisplaysDataType", [{}])
    display = displays[0] if displays else {}
    gpu_cores_str = display.get("sppci_cores", "0")
    try:
        info.gpu_cores = int(gpu_cores_str)
    except ValueError:
        info.gpu_cores = 0

    # Metal family: check newer key first, then fall back
    metal_str = display.get("spdisplays_mtlgpufamilysupport", "") or display.get("spdisplays_metal", "")
    if metal_str:
        # Extract version number: "spdisplays_metal4" -> "4"
        version = metal_str.replace("spdisplays_metal", "").strip()
        info.metal_family = version if version else "Unknown"

    # OS version
    sw = data.get("SPSoftwareDataType", [{}])
    sw_info = sw[0] if sw else {}
    os_ver = sw_info.get("os_version", "")
    if os_ver:
        info.os_version = os_ver

    # ── TDP estimation ────────────────────────────────────────────────────
    info.tdp_w = _TDP_TABLE.get(info.chip_name, 0.0)
    if info.tdp_w == 0.0:
        # Try partial match (e.g., "Apple M1" matches "Apple M1 Pro" prefix)
        for chip, tdp in _TDP_TABLE.items():
            if info.chip_name.startswith(chip):
                info.tdp_w = tdp
                break

    # ── GPU frequency table from IORegistry ───────────────────────────────
    info.gpu_freqs_mhz = get_gpu_freq_table()

    return info
