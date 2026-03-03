"""Temperature and power sensor bindings (IOHIDSensors + SMC)."""

import ctypes
import struct
from ctypes import c_int32, c_int64, c_uint32, c_void_p

from .cfutils import (
    CF,
    CFAllocatorRef,
    CFArrayRef,
    CFDictionaryRef,
    CFStringRef,
    cfdict_get_val,
    cfnum,
    cfrelease,
    cfstr,
    from_cfstr,
    kCFAllocatorDefault,
    kCFTypeDictionaryKeyCallBacks,
    kCFTypeDictionaryValueCallBacks,
)
from .iokit import IOKit, IOServiceIterator, mach_task_self

# ── IOHID bindings ────────────────────────────────────────────────────────────

_iohid_path = "/System/Library/Frameworks/IOKit.framework/IOKit"
# IOHID functions are part of the IOKit framework

IOKit.IOHIDEventSystemClientCreate.argtypes = [CFAllocatorRef]
IOKit.IOHIDEventSystemClientCreate.restype = c_void_p

IOKit.IOHIDEventSystemClientSetMatching.argtypes = [c_void_p, CFDictionaryRef]
IOKit.IOHIDEventSystemClientSetMatching.restype = c_int32

IOKit.IOHIDEventSystemClientCopyServices.argtypes = [c_void_p]
IOKit.IOHIDEventSystemClientCopyServices.restype = CFArrayRef

IOKit.IOHIDServiceClientCopyProperty.argtypes = [c_void_p, CFStringRef]
IOKit.IOHIDServiceClientCopyProperty.restype = CFStringRef

IOKit.IOHIDServiceClientCopyEvent.argtypes = [c_void_p, c_int64, c_int32, c_int64]
IOKit.IOHIDServiceClientCopyEvent.restype = c_void_p

IOKit.IOHIDEventGetFloatValue.argtypes = [c_void_p, c_int64]
IOKit.IOHIDEventGetFloatValue.restype = ctypes.c_double

# IOHID constants
_kHIDPage_AppleVendor = 0xFF00
_kHIDUsage_AppleVendor_TemperatureSensor = 0x0005
_kIOHIDEventTypeTemperature = 15


# ── IOHIDSensors ──────────────────────────────────────────────────────────────


class IOHIDSensors:
    """Read temperature sensors via IOHIDEventSystem (works without sudo)."""

    def __init__(self):
        keys = (c_void_p * 2)(cfstr("PrimaryUsagePage"), cfstr("PrimaryUsage"))
        vals = (c_void_p * 2)(
            cfnum(_kHIDPage_AppleVendor),
            cfnum(_kHIDUsage_AppleVendor_TemperatureSensor),
        )
        self._matching = CF.CFDictionaryCreate(
            kCFAllocatorDefault,
            keys,
            vals,
            2,
            ctypes.byref(kCFTypeDictionaryKeyCallBacks),
            ctypes.byref(kCFTypeDictionaryValueCallBacks),
        )

    def get_temperatures(self) -> list[tuple[str, float]]:
        """Get all temperature sensor readings as (name, celsius) pairs."""
        system = IOKit.IOHIDEventSystemClientCreate(kCFAllocatorDefault)
        if not system:
            return []

        IOKit.IOHIDEventSystemClientSetMatching(system, self._matching)
        services = IOKit.IOHIDEventSystemClientCopyServices(system)
        if not services:
            cfrelease(system)
            return []

        items: list[tuple[str, float]] = []
        count = CF.CFArrayGetCount(services)
        product_key = cfstr("Product")

        for i in range(count):
            sc = CF.CFArrayGetValueAtIndex(services, i)
            if not sc:
                continue

            name_ref = IOKit.IOHIDServiceClientCopyProperty(sc, product_key)
            if not name_ref:
                continue
            name = from_cfstr(name_ref)

            event = IOKit.IOHIDServiceClientCopyEvent(
                sc, _kIOHIDEventTypeTemperature, 0, 0
            )
            if not event:
                continue

            temp = IOKit.IOHIDEventGetFloatValue(
                event, _kIOHIDEventTypeTemperature << 16
            )
            cfrelease(event)
            items.append((name, float(temp)))

        cfrelease(product_key)
        cfrelease(services)
        cfrelease(system)

        items.sort(key=lambda x: x[0])
        return items

    def get_gpu_temp(self) -> float:
        """Get average GPU temperature in Celsius."""
        temps = self.get_temperatures()
        gpu_temps = [t for name, t in temps if "GPU" in name and t > 0]
        if not gpu_temps:
            return 0.0
        return sum(gpu_temps) / len(gpu_temps)

    def get_cpu_temp(self) -> float:
        """Get average CPU temperature in Celsius."""
        temps = self.get_temperatures()
        cpu_temps = [
            t
            for name, t in temps
            if ("pACC" in name or "eACC" in name) and t > 0
        ]
        if not cpu_temps:
            return 0.0
        return sum(cpu_temps) / len(cpu_temps)

    def __del__(self):
        if hasattr(self, "_matching") and self._matching:
            cfrelease(self._matching)


# ── SMC (System Management Controller) ───────────────────────────────────────

# SMC data structures (must match C layout exactly for IOConnectCallStructMethod)

_KEY_DATA_SIZE = 120  # sizeof(KeyData) in macmon


class _KeyDataVer(ctypes.Structure):
    _fields_ = [
        ("major", ctypes.c_uint8),
        ("minor", ctypes.c_uint8),
        ("build", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8),
        ("release", ctypes.c_uint16),
    ]


class _PLimitData(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_uint16),
        ("length", ctypes.c_uint16),
        ("cpu_p_limit", c_uint32),
        ("gpu_p_limit", c_uint32),
        ("mem_p_limit", c_uint32),
    ]


class _KeyInfo(ctypes.Structure):
    _fields_ = [
        ("data_size", c_uint32),
        ("data_type", c_uint32),
        ("data_attributes", ctypes.c_uint8),
    ]


class _KeyData(ctypes.Structure):
    _fields_ = [
        ("key", c_uint32),
        ("vers", _KeyDataVer),
        ("p_limit_data", _PLimitData),
        ("key_info", _KeyInfo),
        ("result", ctypes.c_uint8),
        ("status", ctypes.c_uint8),
        ("data8", ctypes.c_uint8),
        ("data32", c_uint32),
        ("bytes", ctypes.c_uint8 * 32),
    ]


def _fourcc(s: str) -> int:
    """Convert a 4-char string to a FourCC uint32."""
    assert len(s) == 4
    result = 0
    for c in s.encode("ascii"):
        result = (result << 8) | c
    return result


class SMC:
    """Read from the System Management Controller (AppleSMC)."""

    def __init__(self):
        self._conn = c_uint32(0)
        self._keys_cache: dict[int, _KeyInfo] = {}

        for entry, name in IOServiceIterator("AppleSMC"):
            if name == "AppleSMCKeysEndpoint":
                ret = IOKit.IOServiceOpen(
                    entry, mach_task_self(), 0, ctypes.byref(self._conn)
                )
                IOKit.IOObjectRelease(entry)
                if ret != 0:
                    raise RuntimeError(f"IOServiceOpen failed for SMC: {ret}")
                return
            IOKit.IOObjectRelease(entry)

        raise RuntimeError("AppleSMC not found")

    def _read(self, input_data: _KeyData) -> _KeyData:
        """Send a struct method call to SMC."""
        output = _KeyData()
        out_size = ctypes.c_size_t(ctypes.sizeof(_KeyData))
        ret = IOKit.IOConnectCallStructMethod(
            self._conn,
            2,
            ctypes.byref(input_data),
            ctypes.sizeof(_KeyData),
            ctypes.byref(output),
            ctypes.byref(out_size),
        )
        if ret != 0:
            raise RuntimeError(f"SMC read failed: {ret}")
        if output.result == 132:
            raise KeyError("SMC key not found")
        if output.result != 0:
            raise RuntimeError(f"SMC error: {output.result}")
        return output

    def read_key_info(self, key: str) -> _KeyInfo:
        """Read key info (size, type, attributes) for a 4-char SMC key."""
        key_int = _fourcc(key)
        if key_int in self._keys_cache:
            return self._keys_cache[key_int]

        ival = _KeyData()
        ival.data8 = 9
        ival.key = key_int
        oval = self._read(ival)
        self._keys_cache[key_int] = oval.key_info
        return oval.key_info

    def read_val(self, key: str) -> tuple[str, bytes]:
        """Read a value from SMC. Returns (unit_type_fourcc, data_bytes)."""
        ki = self.read_key_info(key)
        key_int = _fourcc(key)

        ival = _KeyData()
        ival.data8 = 5
        ival.key = key_int
        ival.key_info = ki

        oval = self._read(ival)
        data = bytes(oval.bytes[: ki.data_size])
        unit = struct.pack(">I", ki.data_type).decode("ascii", errors="replace")
        return unit, data

    def read_float(self, key: str) -> float:
        """Read a float value from an SMC key."""
        unit, data = self.read_val(key)
        if len(data) == 4:
            return struct.unpack("<f", data)[0]
        return 0.0

    def key_by_index(self, index: int) -> str:
        """Get an SMC key name by index."""
        ival = _KeyData()
        ival.data8 = 8
        ival.data32 = index
        oval = self._read(ival)
        return struct.pack(">I", oval.key).decode("ascii")

    def get_all_keys(self) -> list[str]:
        """Get all available SMC key names."""
        try:
            _, data = self.read_val("#KEY")
            count = struct.unpack(">I", data[:4])[0]
        except Exception:
            return []

        keys = []
        for i in range(count):
            try:
                k = self.key_by_index(i)
                keys.append(k)
            except Exception:
                continue
        return keys

    def close(self):
        if self._conn.value:
            IOKit.IOServiceClose(self._conn)
            self._conn = c_uint32(0)

    def __del__(self):
        self.close()


# ── Temperature via SMC ───────────────────────────────────────────────────────

_FLOAT_TYPE = _fourcc("flt ")

# Known SMC temperature key patterns (avoids enumerating all keys which is slow)
_CPU_TEMP_KEYS = [f"Tp{i:02d}" for i in range(15)] + [f"Te{i:02d}" for i in range(15)]
_GPU_TEMP_KEYS = [f"Tg{i:02d}" for i in range(10)] + [
    f"Tg{c}{d}" for c in "0123" for d in "abcdef0123456789"
]


def _read_smc_temp(smc: SMC, key: str) -> float | None:
    """Try to read a float temperature value from an SMC key. Returns None on failure."""
    try:
        ki = smc.read_key_info(key)
        if ki.data_size != 4 or ki.data_type != _FLOAT_TYPE:
            return None
        val = smc.read_float(key)
        return val if val > 0.0 and val < 150.0 else None  # sanity check
    except Exception:
        return None


def get_smc_temperatures(smc: SMC) -> tuple[float, float]:
    """Get (cpu_temp_avg, gpu_temp_avg) from SMC sensors.

    Probes known temperature key patterns directly instead of enumerating
    all SMC keys (which is very slow).
    CPU: keys 'Tp*' (perf cores) and 'Te*' (efficiency cores).
    GPU: keys 'Tg*'.
    """
    cpu_temps: list[float] = []
    gpu_temps: list[float] = []

    for key in _CPU_TEMP_KEYS:
        val = _read_smc_temp(smc, key)
        if val is not None:
            cpu_temps.append(val)

    for key in _GPU_TEMP_KEYS:
        val = _read_smc_temp(smc, key)
        if val is not None:
            gpu_temps.append(val)

    cpu_avg = sum(cpu_temps) / len(cpu_temps) if cpu_temps else 0.0
    gpu_avg = sum(gpu_temps) / len(gpu_temps) if gpu_temps else 0.0
    return cpu_avg, gpu_avg


def get_system_power(smc: SMC) -> float:
    """Get system power consumption in Watts from SMC (PSTR key)."""
    try:
        return smc.read_float("PSTR")
    except Exception:
        return 0.0
