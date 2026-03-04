"""Tests for SoC info parsing."""

import unittest
from unittest.mock import MagicMock, patch

from apple_smi.soc_info import SocInfo, get_soc_info


class TestSocInfoParsing:
    """Test fast SoC parsing with mock data."""

    def mock_check_output(self, cmd, **kwargs):
        cmd_str = " ".join(cmd)
        if "sysctl" in cmd_str:
            if "hw.model" in cmd_str:
                # Combined call
                return "Mac15,6\nApple M3 Pro\n19327352832\n6\n5"
            return "Unknown"
        elif "sw_vers" in cmd_str:
            if "-productVersion" in cmd_str:
                return "15.3.1"
            if "-buildVersion" in cmd_str:
                return "24D70"
            return ""
        elif "ioreg" in cmd_str:
            if "gpu-core-count" in cmd_str:
                return '"gpu-core-count" = 14'
            return ""
        elif "system_profiler" in cmd_str:
            if "SPDisplaysDataType" in cmd_str:
                return "      Metal Support: Metal 3"
            return ""
        return ""

    @patch("apple_smi.soc_info.get_gpu_freq_table")
    @patch("subprocess.check_output")
    def test_parse_m3_pro(self, mock_check_output, mock_freq):
        mock_check_output.side_effect = self.mock_check_output
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
    @patch("subprocess.check_output")
    def test_empty_output(self, mock_check_output, mock_freq):
        mock_check_output.return_value = ""
        mock_freq.return_value = []

        info = get_soc_info()

        assert info.chip_name == "Unknown"
        assert info.memory_gb == 0
        assert info.gpu_cores == 0

    @patch("apple_smi.soc_info.get_gpu_freq_table")
    @patch("subprocess.check_output")
    def test_exception_handling(self, mock_check_output, mock_freq):
        mock_check_output.side_effect = Exception("failed")
        mock_freq.return_value = []

        info = get_soc_info()

        # Should gracefully handle errors
        assert info.chip_name == "Unknown"
        assert info.memory_gb == 0
