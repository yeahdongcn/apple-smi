# 🍎 apple-smi

**nvidia-smi equivalent for Apple Silicon** – High-performance, sudoless GPU monitoring with zero dependencies.

```text
$ apple-smi
Wed Mar 04 14:52:00 2026
+-----------------------------------------------------------------------------------------+
| APPLE-SMI 0.1.1              macOS Version: 26.3 (25D125)              Metal Version: 3 |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                               |                 Disp.A |                      |
|      Temp                 Pwr:Usage/Cap |           Memory-Usage |             GPU-Util |
|=========================================+========================+======================|
|   0  Apple M1 (8-Core GPU)              |                     On |                      |
|       30C                    2.4W / 20W |    13826MiB / 16384MiB |                  12% |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
| GPU           PID  Type   Process name                                       GPU Memory |
|                                                                                   Usage |
|=========================================================================================|
|   0         72743    C    python3.11                                             530MiB |
|   0          1007    G    NotificationCenter                                     170MiB |
|   0          3197    G    WeType                                                 216MiB |
+-----------------------------------------------------------------------------------------+
```

## ✨ Features

- 🚫 **No sudo required** – Uses private macOS APIs (`IOReport`, `IOHIDSensors`, `SMC`) for sudoless operation.
- ⚡ **Ultra-Fast & Lightweight** – Optimized startup (<50ms) using targeted `sysctl` and `ioreg` calls.
- 🔋 **Power Monitoring** – Displays SoC power consumption (Usage) against chip TDP (Cap).
- 🌡️ **Smart Thermals** – High-accuracy GPU/SOC temperature readings with sensor fallback logic.
- 📋 **Robust Process Listing** – Lists active GPU processes with full name resolution (no truncation for paths with spaces).
- 🔍 **C/G Classification** – Categorizes processes by Type (`C` for Compute, `G` for Graphics).
- 💾 **Memory Usage** – Detailed breakdown of unified memory utilization.
- 🔄 **Watch Compatible** – Default **100ms** sampling interval for smooth real-time monitoring.
- 📦 **Zero Dependencies** – Pure Python, utilizing `ctypes` to interface with macOS frameworks.

## 📥 Installation

```bash
pip install apple-smi
```

## 🚀 Usage

### Command Line Options

```bash
# Basic usage
apple-smi

# Set sampling interval (default: 100ms)
apple-smi --interval 250

# JSON output for integration with other tools
apple-smi --json

# Continuous monitoring (highly recommended)
watch -n 0.1 apple-smi
```

### Process Filtering

By default, `apple-smi` only shows **Compute (C)** processes (e.g., Python, MLX, Torch, llama.cpp) to reduce system noise. You can show all GPU-connected processes (including window compositors and browsers) using an environment variable:

```bash
APPLE_SMI_SHOW_ALL_PROCESSES=1 apple-smi
```

### Backends

`apple-smi` automatically selects the best available backend:

1. **IOKit (Default)**: Uses undocumented IOKit APIs for **sudoless** monitoring.
2. **Powermetrics (Fallback)**: Uses the system `powermetrics` tool (requires `sudo` or root privileges).

| Variable | Values | Description |
|----------|--------|-------------|
| `APPLE_SMI_BACKEND` | `iokit`, `powermetrics` | Force a specific backend. Default: auto-detect. |
| `APPLE_SMI_SHOW_ALL_PROCESSES` | `0`, `1` | Show all GPU processes (G+C). Default: `0`. |

## 🔧 Requirements

- macOS on Apple Silicon (M1, M2, M3, M4, M5)
- Python 3.10+

## 📝 License

MIT License – see [LICENSE](LICENSE) for details.
