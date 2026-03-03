# 🍎 apple-smi

**nvidia-smi equivalent for macOS Apple Silicon** – Monitor Metal GPU usage, power consumption, and temperature from your terminal.

```
$ apple-smi
Tue Mar  3 15:39:42 2026
+-----------------------------------------------------------------------------------------+
| apple-smi 0.1.0                   macOS 15.3.1              Metal Support: Metal 3      |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                   Chip        | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  Apple M3 Pro (14-Core GPU)     On  |   Apple Silicon     On |                  N/A |
|  N/A  52C    P0             8W /   22W  |   9012MiB /  18432MiB  |     45%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|                                       No running processes found                        |
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

## 🔧 Requirements

- macOS on Apple Silicon (M1/M2/M3/M4)
- Python 3.10+

## 📝 License

MIT License – see [LICENSE](LICENSE) for details.
