# 🍎 apple-smi

**nvidia-smi equivalent for macOS Apple Silicon** – Monitor Metal GPU usage, power consumption, and temperature from your terminal.

```
$ apple-smi
Wed Mar 04 10:15:39 2026
+-----------------------------------------------------------------------------------------+
| APPLE-SMI 0.1.0              macOS Version: 26.3 (25D125)              Metal Version: 4 |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                               |                 Disp.A |                      |
|      Temp                 Pwr:Usage/Cap |           Memory-Usage |             GPU-Util |
|=========================================+========================+======================|
|   0  Apple M1 (8-Core GPU)              |                     On |                      |
|       30C                   11.4W / 20W |    13864MiB / 16384MiB |                   5% |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
| GPU     PID   Type   Process name                                            GPU Memory |
|                                                                                   Usage |
|=========================================================================================|
|   0    72743     C      python3.11                                               530MiB |
|   0    72807     C      python3.11                                               349MiB |
|   0    72808     C      python3.11                                               349MiB |
+-----------------------------------------------------------------------------------------+
```

## ✨ Features

- 🚫 **No sudo required** – Uses private macOS APIs (`IOReport`, `IOHIDSensors`, `SMC`) for sudoless operation.
- ⚡ **GPU Metrics** – Real-time GPU usage percentage, frequency, and Metal version.
- 🔋 **Power Monitoring** – Displays SoC power consumption (Usage) against chip TDP (Cap).
- 🌡️ **Temperature** – GPU temperature readings directly from system sensors.
- 💾 **Memory Usage** – Detailed breakdown of unified memory utilization.
- 📊 **nvidia-smi Style** – Familiar box-drawing table format that fits perfectly in your workflows.
- 📋 **Process Listing** – Lists active GPU processes, categorized by Type (`C` for Compute, `G` for Graphics).
- 🔄 **Watch Compatible** – Works perfectly with `watch -n 0.1 apple-smi`.
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

# Set sampling interval (default: 1000ms)
apple-smi --interval 500

# JSON output for integration with other tools
apple-smi --json

# Continuous monitoring
watch -n 0.5 apple-smi
```

### Process Filtering

By default, `apple-smi` only shows **Compute (C)** processes (e.g., Python, MLX, llama.cpp) to reduce noise. You can show all GPU-connected processes (including window compositors and browsers) using an environment variable.

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

- macOS on Apple Silicon (M1, M2, M3, M4)
- Python 3.10+

## 📝 License

MIT License – see [LICENSE](LICENSE) for details.
