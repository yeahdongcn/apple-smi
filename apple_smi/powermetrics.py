"""Fallback backend: parse powermetrics output (requires sudo)."""

import re
import subprocess
from dataclasses import field

from .memory import MemoryInfo, get_memory_info
from .sampler import Metrics
from .soc_info import SocInfo, get_soc_info


class PowermetricsSampler:
    """Gather GPU metrics by parsing `sudo powermetrics` output."""

    def __init__(self):
        self.soc = get_soc_info()

    def get_metrics(self, duration_ms: int = 1000) -> Metrics:
        """Run powermetrics and parse the output into Metrics."""
        m = Metrics()

        try:
            result = subprocess.run(
                [
                    "powermetrics",
                    "--samplers", "gpu_power,gpu",
                    "-i", str(duration_ms),
                    "-n", "1",
                ],
                capture_output=True,
                text=True,
                timeout=max(duration_ms / 1000 + 5, 10),
            )
            output = result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            m.memory = get_memory_info()
            return m

        # Parse GPU power
        # Example: "GPU Power: 1234 mW"
        gpu_power_match = re.search(r"GPU Power:\s+([\d.]+)\s*mW", output)
        if gpu_power_match:
            m.gpu_power_w = float(gpu_power_match.group(1)) / 1000.0

        # Parse GPU utilization
        # Example: "GPU active residency:  45.00%"
        gpu_util_match = re.search(
            r"GPU\s+(?:active\s+)?residency:\s+([\d.]+)\s*%", output
        )
        if gpu_util_match:
            m.gpu_usage_pct = float(gpu_util_match.group(1))

        # Parse GPU frequency
        # Example: "GPU active frequency: 1398 MHz"
        gpu_freq_match = re.search(
            r"GPU\s+(?:active\s+)?frequency:\s+([\d.]+)\s*MHz", output
        )
        if gpu_freq_match:
            m.gpu_freq_mhz = int(float(gpu_freq_match.group(1)))

        # Parse CPU power
        cpu_power_match = re.search(r"CPU Power:\s+([\d.]+)\s*mW", output)
        if cpu_power_match:
            m.cpu_power_w = float(cpu_power_match.group(1)) / 1000.0

        # Parse ANE power
        ane_power_match = re.search(r"ANE Power:\s+([\d.]+)\s*mW", output)
        if ane_power_match:
            m.ane_power_w = float(ane_power_match.group(1)) / 1000.0

        # Parse combined/package power
        pkg_power_match = re.search(
            r"(?:Combined|Package)\s+Power.*?:\s+([\d.]+)\s*mW", output
        )
        if pkg_power_match:
            m.total_power_w = float(pkg_power_match.group(1)) / 1000.0
        else:
            m.total_power_w = m.cpu_power_w + m.gpu_power_w + m.ane_power_w

        # Memory (always available without sudo)
        m.memory = get_memory_info()

        # Try to get temperature via IOHIDSensors (works without sudo)
        try:
            from .sensors import IOHIDSensors
            hid = IOHIDSensors()
            cpu_temp, gpu_temp = hid.get_cpu_gpu_temps()
            m.cpu_temp_c = cpu_temp
            m.gpu_temp_c = gpu_temp
        except Exception:
            m.cpu_temp_c = 0.0
            m.gpu_temp_c = 0.0

        return m
