"""nvidia-smi style box-drawing output formatter."""

import json
from datetime import datetime

from . import __version__
from .sampler import Metrics
from .soc_info import SocInfo


def _bytes_to_mib(b: int) -> int:
    """Convert bytes to MiB."""
    return b // (1024 * 1024)



def format_table(metrics: Metrics, soc: SocInfo) -> str:
    """Format metrics as an nvidia-smi style box-drawing table."""
    lines: list[str] = []

    # Timestamp
    now = datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    lines.append(now)

    # ── Header box ────────────────────────────────────────────────────────
    # Width: 89 chars inner (matching nvidia-smi width)
    W = 89

    lines.append("+" + "-" * W + "+")

    # Row 1: apple-smi version | macOS version | Metal version
    os_ver = soc.os_version if soc.os_version else "macOS"
    if os_ver.startswith("macOS "):
        os_ver = "macOS Version: " + os_ver[6:]
    elif not os_ver.startswith("macOS Version:"):
        os_ver = f"macOS Version: {os_ver}"
    
    # Shorten os_ver if it's too long
    if len(os_ver) > 35:
        os_ver = os_ver[:32] + ".."
    
    metal = f"Metal Version: {soc.metal_family}"

    col1 = f" APPLE-SMI {__version__}"
    col2 = os_ver
    col3 = metal

    # Distribute space: col1 left, col2 center, col3 right (docked with 1 space)
    # Total width (W) = len(col1) + gap1 + len(col2) + gap2 + len(col3) + 1 space
    remaining = W - len(col1) - len(col2) - len(col3) - 1
    gap1 = remaining // 2
    gap2 = remaining - gap1
    header_line = f"|{col1}{' ' * gap1}{col2}{' ' * gap2}{col3} |"
    lines.append(header_line)

    # ── GPU info box ──────────────────────────────────────────────────────
    # Three columns matching nvidia-smi widths
    C1, C2, C3 = 41, 24, 22

    lines.append("+" + "-" * C1 + "+" + "-" * C2 + "+" + "-" * C3 + "+")

    # Sub-column layout within C1 (41 chars):
    #   margin(1) + GPU/idx(3) + gap(2) + Name/value(34) + margin(1) = 41
    # Row 2 sub-columns within C1:
    #   pad(6) + Temp(4) + Pwr:Usage/Cap(30) + margin(1) = 41
    IDX_W = 3
    IDX_GAP = 2
    NAME_W = C1 - 1 - IDX_W - IDX_GAP - 1  # 34
    TEMP_PAD = 1 + IDX_W + IDX_GAP          # 6
    TEMP_W = 4
    PWR_W = C1 - TEMP_PAD - TEMP_W - 1      # 30

    # Header row 1: GPU  Name  |  Disp.A  |  (empty)
    h1c1 = f" {'GPU':>{IDX_W}s}{'':>{IDX_GAP}s}{'Name':<{NAME_W}s} "
    h1c2 = f" {'Disp.A':>{C2 - 2}s} "
    h1c3 = " " * C3
    lines.append(f"|{h1c1}|{h1c2}|{h1c3}|")

    # Header row 2: Temp  Pwr:Usage/Cap  |  Memory-Usage  |  GPU-Util
    h2c1 = f"{'':>{TEMP_PAD}s}{'Temp':>{TEMP_W}s}{'Pwr:Usage/Cap':>{PWR_W}s} "
    h2c2 = f" {'Memory-Usage':>{C2 - 2}s} "
    h2c3 = f" {'GPU-Util':>{C3 - 2}s} "
    lines.append(f"|{h2c1}|{h2c2}|{h2c3}|")

    # Separator
    lines.append("|" + "=" * C1 + "+" + "=" * C2 + "+" + "=" * C3 + "|")

    # ── GPU data rows (aligned to sub-columns above) ────────────────────
    gpu_name = soc.chip_name
    if soc.gpu_cores > 0:
        gpu_name += f" ({soc.gpu_cores}-Core GPU)"
    if len(gpu_name) > NAME_W:
        gpu_name = gpu_name[: NAME_W - 2] + ".."

    # Data row 1: idx  gpu_name  |  On  |  (empty)
    d1c1 = f" {0:>{IDX_W}d}{'':>{IDX_GAP}s}{gpu_name:<{NAME_W}s} "
    d1c2 = f" {'On':>{C2 - 2}s} "
    d1c3 = " " * C3
    lines.append(f"|{d1c1}|{d1c2}|{d1c3}|")

    # Data row 2: temp  pwr  |  memory  |  gpu-util
    temp_str = f"{int(metrics.gpu_temp_c)}C" if metrics.gpu_temp_c > 0 else "N/A"
    pwr_str = f"{metrics.gpu_power_w:.0f}W / {metrics.total_power_w:.0f}W"
    d2c1 = f"{'':>{TEMP_PAD}s}{temp_str:>{TEMP_W}s}{pwr_str:>{PWR_W}s} "

    mem_used = _bytes_to_mib(metrics.memory.ram_used)
    mem_total = _bytes_to_mib(metrics.memory.ram_total)
    mem_str = f"{mem_used}MiB / {mem_total}MiB"
    d2c2 = f" {mem_str:>{C2 - 2}s} "

    gpu_util_str = f"{metrics.gpu_usage_pct:.0f}%"
    d2c3 = f" {gpu_util_str:>{C3 - 2}s} "
    lines.append(f"|{d2c1}|{d2c2}|{d2c3}|")

    # Close GPU box
    lines.append("+" + "-" * C1 + "+" + "-" * C2 + "+" + "-" * C3 + "+")

    # ── Processes box ─────────────────────────────────────────────────────
    lines.append("")
    lines.append("+" + "-" * W + "+")
    lines.append(f"|{' Processes:':<{W}s}|")
    lines.append(f"|{'  GPU   GI   CI              PID   Type   Process name                        GPU Memory ':<{W}s}|")
    lines.append(f"|{'        ID   ID                                                               Usage      ':<{W}s}|")
    lines.append("|" + "=" * W + "|")
    lines.append(f"|{'No running processes found':^{W}s}|")
    lines.append("+" + "-" * W + "+")

    return "\n".join(lines)


def format_json(metrics: Metrics, soc: SocInfo) -> str:
    """Format metrics as JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "version": __version__,
        "gpu": {
            "name": soc.chip_name,
            "gpu_cores": soc.gpu_cores,
            "frequency_mhz": metrics.gpu_freq_mhz,
            "utilization_pct": round(metrics.gpu_usage_pct, 1),
            "temperature_c": round(metrics.gpu_temp_c, 1),
            "power_w": round(metrics.gpu_power_w, 2),
        },
        "power": {
            "cpu_w": round(metrics.cpu_power_w, 2),
            "gpu_w": round(metrics.gpu_power_w, 2),
            "ane_w": round(metrics.ane_power_w, 2),
            "total_w": round(metrics.total_power_w, 2),
            "system_w": round(metrics.sys_power_w, 2),
        },
        "memory": {
            "ram_used_bytes": metrics.memory.ram_used,
            "ram_total_bytes": metrics.memory.ram_total,
            "ram_used_mib": _bytes_to_mib(metrics.memory.ram_used),
            "ram_total_mib": _bytes_to_mib(metrics.memory.ram_total),
            "swap_used_bytes": metrics.memory.swap_used,
            "swap_total_bytes": metrics.memory.swap_total,
        },
        "soc": {
            "chip_name": soc.chip_name,
            "mac_model": soc.mac_model,
            "memory_gb": soc.memory_gb,
            "gpu_cores": soc.gpu_cores,
            "ecpu_cores": soc.ecpu_cores,
            "pcpu_cores": soc.pcpu_cores,
            "metal_family": soc.metal_family,
            "os_version": soc.os_version,
        },
    }
    return json.dumps(data, indent=2)
