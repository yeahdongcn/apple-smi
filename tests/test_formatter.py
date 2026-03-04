"""Tests for the box-drawing formatter."""

import json
from unittest.mock import patch

from apple_smi.formatter import format_json, format_table
from apple_smi.memory import MemoryInfo
from apple_smi.processes import ProcessInfo
from apple_smi.sampler import Metrics
from apple_smi.soc_info import SocInfo


def _make_soc() -> SocInfo:
    return SocInfo(
        chip_name="Apple M3 Pro",
        mac_model="Mac15,6",
        memory_gb=18,
        ecpu_cores=4,
        pcpu_cores=6,
        gpu_cores=14,
        gpu_freqs_mhz=[444, 612, 808, 1000, 1164, 1398],
        metal_family="3",
        os_version="macOS 15.3.1",
    )


def _make_metrics() -> Metrics:
    return Metrics(
        gpu_freq_mhz=1200,
        gpu_usage_pct=45.2,
        gpu_power_w=8.5,
        gpu_temp_c=52.0,
        cpu_power_w=3.2,
        ane_power_w=0.0,
        total_power_w=11.7,
        sys_power_w=15.0,
        memory=MemoryInfo(
            ram_total=18 * 1024 * 1024 * 1024,  # 18 GB
            ram_used=9 * 1024 * 1024 * 1024,  # 9 GB
            swap_total=2 * 1024 * 1024 * 1024,
            swap_used=512 * 1024 * 1024,
        ),
    )


class TestFormatTable:
    def test_basic_output(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_table(metrics, soc)

        # Should contain key elements
        assert "APPLE-SMI" in output
        assert "Apple M3 Pro" in output
        assert "Metal Version: 3" in output
        assert "14-Core GPU" in output
        assert "52C" in output
        assert "45%" in output
        assert "MiB" in output
        assert "macOS Version:" in output

    def test_box_drawing_structure(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_table(metrics, soc)
        lines = output.split("\n")

        # Should have box drawing characters
        assert any("+" in line and "-" in line for line in lines)
        assert any("|" in line for line in lines)
        assert any("=" in line for line in lines)

    def test_processes_section(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_table(metrics, soc)

        assert "Processes:" in output
        assert "No running processes found" in output

    def test_zero_temp(self):
        soc = _make_soc()
        metrics = _make_metrics()
        metrics.gpu_temp_c = 0.0
        output = format_table(metrics, soc)

        assert "N/A" in output

    def test_high_utilization(self):
        soc = _make_soc()
        metrics = _make_metrics()
        metrics.gpu_usage_pct = 95.0
        output = format_table(metrics, soc)

        assert "95%" in output

    def test_consistent_line_widths(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_table(metrics, soc)
        lines = output.split("\n")

        # All box lines (starting with | or +) should be same width
        box_lines = [l for l in lines if l.startswith("|") or l.startswith("+")]
        if box_lines:
            widths = set(len(l) for l in box_lines)
            # There should be at most 2 different widths
            # (header full-width vs gpu-info 3-column)
            assert len(widths) <= 2


class TestFormatJson:
    def test_valid_json(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_json(metrics, soc)

        data = json.loads(output)
        assert isinstance(data, dict)

    def test_json_fields(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_json(metrics, soc)

        data = json.loads(output)
        assert "gpu" in data
        assert "power" in data
        assert "memory" in data
        assert "soc" in data
        assert "timestamp" in data
        assert "version" in data

    def test_json_gpu_data(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_json(metrics, soc)

        data = json.loads(output)
        gpu = data["gpu"]
        assert gpu["name"] == "Apple M3 Pro"
        assert gpu["gpu_cores"] == 14
        assert gpu["utilization_pct"] == 45.2
        assert gpu["temperature_c"] == 52.0

    def test_json_memory_data(self):
        soc = _make_soc()
        metrics = _make_metrics()
        output = format_json(metrics, soc)

        data = json.loads(output)
        mem = data["memory"]
        assert mem["ram_total_mib"] == 18 * 1024
        assert mem["ram_used_mib"] == 9 * 1024

    def test_json_processes(self):
        soc = _make_soc()
        metrics = _make_metrics()
        metrics.processes = [
            ProcessInfo(pid=1234, name="TestApp", type="G", memory_usage_bytes=100 * 1024 * 1024),
        ]
        output = format_json(metrics, soc)
        data = json.loads(output)
        assert "processes" in data
        assert len(data["processes"]) == 1
        assert data["processes"][0]["pid"] == 1234


class TestProcessDisplay:
    def test_processes_with_data(self):
        soc = _make_soc()
        metrics = _make_metrics()
        metrics.processes = [
            ProcessInfo(pid=636, name="WindowServer", type="G", memory_usage_bytes=120 * 1024 * 1024),
            ProcessInfo(pid=1234, name="Chrome", type="G", memory_usage_bytes=250 * 1024 * 1024),
        ]
        output = format_table(metrics, soc)

        assert "No running processes found" not in output
        assert "636" in output
        assert "WindowServer" in output
        assert "1234" in output
        assert "Chrome" in output
        assert "250MiB" in output
        assert "120MiB" in output

    def test_no_processes(self):
        soc = _make_soc()
        metrics = _make_metrics()
        metrics.processes = []
        output = format_table(metrics, soc)

        assert "No running processes found" in output
