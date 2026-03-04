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

- 🚫 **No sudo required** – Uses private macOS APIs (IOReport, IOHIDSensors, SMC) for sudoless operation
- ⚡ **GPU utilization** – Real-time GPU usage percentage and frequency
- 🔋 **Power monitoring** – GPU, CPU, and ANE power consumption in Watts
- 🌡️ **Temperature** – GPU and CPU temperature readings
- 💾 **Memory usage** – Unified memory utilization
- 📊 **nvidia-smi style output** – Familiar box-drawing table format
- 🔄 **watch compatible** – Works perfectly with `watch -n 0.1 apple-smi`
- 📦 **Zero dependencies** – Pure Python, no external packages required

## 📥 Installation

```bash
pip install apple-smi
```

## 🚀 Usage

```bash
# Basic usage
apple-smi

# Continuous monitoring (using watch)
watch -n 0.1 apple-smi

# JSON output
apple-smi --json
```

### Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| `APPLE_SMI_BACKEND` | `iokit`, `powermetrics` | Force a specific backend. Default: auto-detect |
| `APPLE_SMI_SHOW_ALL_PROCESSES` | `0`, `1` | Show all GPU processes (G+C). Default: `0` (Compute only) |

## 🔧 Requirements

- macOS on Apple Silicon (M1/M2/M3/M4)
- Python 3.10+

## 📝 License

MIT License – see [LICENSE](LICENSE) for details.
