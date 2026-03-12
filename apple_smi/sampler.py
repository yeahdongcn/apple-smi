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
    cpu_temp_c: float = 0.0
    cpu_power_w: float = 0.0
    ane_power_w: float = 0.0
    dram_power_w: float = 0.0
    gpu_sram_power_w: float = 0.0
    total_power_w: float = 0.0  # max(system_power, component_sum)
    sys_power_w: float = 0.0    # residual = total - component_sum
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    processes: list[ProcessInfo] = field(default_factory=list)


def _zero_div(a: float, b: float) -> float:
    return a / b if b != 0 else 0.0


def _calc_freq_usage(
    residencies: list[tuple[str, int]], freqs: list[int]
) -> tuple[int, float]:
    """Calculate average frequency and active utilization from residency data.

    Uses the same algorithm as mactop: GPU active % = activeTime / totalTime * 100,
    and weighted average frequency across active states only.

    Returns (avg_freq_mhz, active_percent_0_to_100).
    """
    if not residencies or not freqs:
        return 0, 0.0

    total_time = 0
    active_time = 0
    weighted_freq = 0.0
    active_state_idx = 0

    for name, residency in residencies:
        total_time += residency
        if name not in ("IDLE", "DOWN", "OFF"):
            active_time += residency
            if active_state_idx < len(freqs):
                weighted_freq += freqs[active_state_idx] * residency
            active_state_idx += 1

    if total_time == 0:
        return 0, 0.0

    active_pct = (active_time / total_time) * 100.0

    avg_freq = 0
    if active_time > 0 and len(freqs) > 0:
        avg_freq = int(weighted_freq / active_time)

    return avg_freq, active_pct


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

    def get_metrics(self, duration_ms: int = 100) -> Metrics:
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
                elif ch.startswith("DRAM"):
                    m.dram_power_w += compute_watts(x.simple_value, x.unit, dt)
                elif ch.startswith("GPU SRAM"):
                    m.gpu_sram_power_w += compute_watts(x.simple_value, x.unit, dt)

        # Aggregate GPU usage
        if gpu_usages:
            m.gpu_freq_mhz = int(
                sum(f for f, _ in gpu_usages) / len(gpu_usages)
            )
            # _calc_freq_usage now returns active_percent directly (0-100)
            m.gpu_usage_pct = (
                sum(u for _, u in gpu_usages) / len(gpu_usages)
            )

        # Power calculation matching mactop:
        # componentSum = CPU + GPU + ANE + DRAM + GPU_SRAM
        # totalPower = max(systemPower, componentSum)
        # systemResidual = totalPower - componentSum
        component_sum = (
            m.cpu_power_w + m.gpu_power_w + m.ane_power_w
            + m.dram_power_w + m.gpu_sram_power_w
        )

        # Temperature: try SMC first, fall back to HID sensors
        cpu_temp = 0.0
        gpu_temp = 0.0
        system_power = 0.0

        if self._smc_available and self._smc:
            try:
                cpu_temp, gpu_temp = get_smc_temperatures(self._smc)
            except Exception:
                pass
            try:
                system_power = get_system_power(self._smc)
            except Exception:
                pass

        # HID fallback for temps SMC didn't provide (matching mactop)
        if cpu_temp <= 0.0 or gpu_temp <= 0.0:
            try:
                hid_cpu, hid_gpu = self._hid.get_cpu_gpu_temps()
                if cpu_temp <= 0.0:
                    cpu_temp = hid_cpu
                if gpu_temp <= 0.0:
                    gpu_temp = hid_gpu
            except Exception:
                pass

        m.cpu_temp_c = cpu_temp
        m.gpu_temp_c = gpu_temp

        # Match mactop: total = max(system, components), sys = residual
        total_power = system_power
        if total_power < component_sum:
            total_power = component_sum
        m.total_power_w = total_power
        m.sys_power_w = total_power - component_sum

        # Memory
        m.memory = get_memory_info()

        # Processes
        show_all = os.environ.get("APPLE_SMI_SHOW_ALL_PROCESSES", "0") == "1"
        m.processes = get_gpu_processes(show_all=show_all)

        return m
