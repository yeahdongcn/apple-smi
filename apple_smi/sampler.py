"""Metrics sampler – combines IOReport, sensors, and memory into unified metrics."""

import os
from dataclasses import dataclass, field

from .ioreport import IOReportSampler, compute_watts
from .memory import MemoryInfo, get_memory_info
from .processes import ProcessInfo, get_gpu_processes
from .sensors import IOHIDSensors, SMC, get_smc_temperatures, get_system_power
from .soc_info import SocInfo, get_soc_info

# IOReport channel/subgroup constants
_CPU_FREQ_CORE_SUBG = "CPU Core Performance States"
_GPU_FREQ_DICE_SUBG = "GPU Performance States"


@dataclass
class Metrics:
    """Aggregated system metrics snapshot."""

    gpu_freq_mhz: int = 0
    gpu_usage_pct: float = 0.0  # 0–100
    gpu_power_w: float = 0.0
    gpu_temp_c: float = 0.0
    cpu_power_w: float = 0.0
    ane_power_w: float = 0.0
    total_power_w: float = 0.0
    sys_power_w: float = 0.0
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    processes: list[ProcessInfo] = field(default_factory=list)


def _zero_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0


def _calc_freq_usage(
    residencies: list[tuple[str, int]], freqs: list[int]
) -> tuple[int, float]:
    """Calculate average frequency and utilization fraction from residency data.

    Returns (avg_freq_mhz, usage_fraction_0_to_1).
    """
    if not residencies or not freqs:
        return 0, 0.0

    # Find offset: skip IDLE/DOWN/OFF states
    offset = 0
    for i, (name, _) in enumerate(residencies):
        if name not in ("IDLE", "DOWN", "OFF"):
            offset = i
            break

    total = sum(v for _, v in residencies)
    active = sum(v for _, v in residencies[offset:])

    if total == 0 or active == 0:
        return 0, 0.0

    # Calculate weighted average frequency
    count = min(len(freqs), len(residencies) - offset)
    avg_freq = 0.0
    for i in range(count):
        pct = _zero_div(float(residencies[i + offset][1]), float(active))
        avg_freq += pct * freqs[i]

    usage_ratio = _zero_div(float(active), float(total))
    max_freq = freqs[-1] if freqs else 1
    min_freq = freqs[0] if freqs else 0
    from_max = (max(avg_freq, min_freq) * usage_ratio) / max_freq if max_freq > 0 else 0.0

    return int(avg_freq), from_max


class Sampler:
    """High-level metrics sampler using IOReport + sensors."""

    def __init__(self):
        self.soc = get_soc_info()

        # IOReport channels
        channels = [
            ("Energy Model", None),
            ("CPU Stats", _CPU_FREQ_CORE_SUBG),
            ("GPU Stats", _GPU_FREQ_DICE_SUBG),
        ]
        self._ior = IOReportSampler(channels)

        # Temperature sensors
        self._hid = IOHIDSensors()
        self._smc: SMC | None = None
        self._smc_available = False
        try:
            self._smc = SMC()
            # Quick test: try reading a key to confirm SMC works
            self._smc.read_key_info("#KEY")
            self._smc_available = True
        except Exception:
            self._smc_available = False

    def get_metrics(self, duration_ms: int = 1000) -> Metrics:
        """Sample metrics over the given duration. Returns aggregated Metrics."""
        items = self._ior.get_sample(duration_ms)
        dt = duration_ms

        m = Metrics()

        gpu_usages: list[tuple[int, float]] = []

        for x in items:
            # GPU frequency / utilization
            if x.group == "GPU Stats" and x.subgroup == _GPU_FREQ_DICE_SUBG:
                if x.channel == "GPUPH":
                    gpu_freqs = self.soc.gpu_freqs_mhz
                    if len(gpu_freqs) > 1:
                        gpu_freqs = gpu_freqs[1:]  # Skip first (lowest) state
                    freq, usage = _calc_freq_usage(x.residencies, gpu_freqs)
                    gpu_usages.append((freq, usage))

            # Power (Energy Model channel)
            if x.group == "Energy Model":
                ch = x.channel
                if ch == "GPU Energy":
                    m.gpu_power_w += compute_watts(x.simple_value, x.unit, dt)
                elif ch.endswith("CPU Energy"):
                    m.cpu_power_w += compute_watts(x.simple_value, x.unit, dt)
                elif ch.startswith("ANE"):
                    m.ane_power_w += compute_watts(x.simple_value, x.unit, dt)

        # Aggregate GPU usage
        if gpu_usages:
            m.gpu_freq_mhz = int(
                sum(f for f, _ in gpu_usages) / len(gpu_usages)
            )
            m.gpu_usage_pct = (
                sum(u for _, u in gpu_usages) / len(gpu_usages) * 100.0
            )

        m.total_power_w = m.cpu_power_w + m.gpu_power_w + m.ane_power_w

        # Temperature: try SMC first, fall back to HID sensors
        gpu_temp = 0.0
        if self._smc_available and self._smc:
            try:
                _, gpu_temp = get_smc_temperatures(self._smc)
            except Exception:
                pass
            try:
                m.sys_power_w = get_system_power(self._smc)
            except Exception:
                pass

        # If SMC didn't provide GPU temp, try HID sensors
        if gpu_temp <= 0.0:
            try:
                gpu_temp = self._hid.get_gpu_temp()
            except Exception:
                pass

        m.gpu_temp_c = gpu_temp

        # Memory
        m.memory = get_memory_info()

        # Processes
        show_all = os.environ.get("APPLE_SMI_SHOW_ALL_PROCESSES", "0") == "1"
        m.processes = get_gpu_processes(show_all=show_all)

        return m
