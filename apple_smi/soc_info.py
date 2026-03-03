"""SoC information from system_profiler and IORegistry."""

import json
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

    # ── GPU frequency table from IORegistry ───────────────────────────────
    info.gpu_freqs_mhz = get_gpu_freq_table()

    return info
