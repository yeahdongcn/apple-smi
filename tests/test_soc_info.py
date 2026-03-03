"""Tests for SoC info parsing."""

import json
from unittest.mock import MagicMock, patch

from apple_smi.soc_info import SocInfo, get_soc_info


class TestSocInfoParsing:
    """Test system_profiler JSON parsing with mock data."""

    MOCK_PROFILER_OUTPUT = json.dumps(
        {
            "SPHardwareDataType": [
                {
                    "chip_type": "Apple M3 Pro",
                    "machine_model": "Mac15,6",
                    "physical_memory": "18 GB",
                    "number_processors": "proc 11:6:5",
                }
            ],
            "SPDisplaysDataType": [
                {
                    "sppci_cores": "14",
                    "spdisplays_mtlgpufamilysupport": "spdisplays_metal3",
                }
            ],
            "SPSoftwareDataType": [
                {
                    "os_version": "macOS 15.3.1 (24D70)",
                }
            ],
        }
    )

    @patch("apple_smi.soc_info.get_gpu_freq_table")
    @patch("subprocess.run")
    def test_parse_m3_pro(self, mock_run, mock_freq):
        mock_result = MagicMock()
        mock_result.stdout = self.MOCK_PROFILER_OUTPUT
        mock_run.return_value = mock_result
        mock_freq.return_value = [444, 612, 808, 1000, 1164, 1398]

        info = get_soc_info()

        assert info.chip_name == "Apple M3 Pro"
        assert info.mac_model == "Mac15,6"
        assert info.memory_gb == 18
        assert info.pcpu_cores == 6
        assert info.ecpu_cores == 5
        assert info.gpu_cores == 14
        assert info.metal_family == "3"
        assert "15.3.1" in info.os_version
        assert info.gpu_freqs_mhz == [444, 612, 808, 1000, 1164, 1398]

    @patch("apple_smi.soc_info.get_gpu_freq_table")
    @patch("subprocess.run")
    def test_empty_profiler_output(self, mock_run, mock_freq):
        mock_result = MagicMock()
        mock_result.stdout = "{}"
        mock_run.return_value = mock_result
        mock_freq.return_value = []

        info = get_soc_info()

        assert info.chip_name == "Unknown"
        assert info.memory_gb == 0
        assert info.gpu_cores == 0

    @patch("apple_smi.soc_info.get_gpu_freq_table")
    @patch("subprocess.run")
    def test_profiler_exception(self, mock_run, mock_freq):
        mock_run.side_effect = FileNotFoundError("system_profiler not found")
        mock_freq.return_value = []

        info = get_soc_info()

        # Should gracefully handle errors
        assert info.chip_name == "Unknown"
        assert info.memory_gb == 0
