"""IOKit framework bindings via ctypes for Apple Silicon hardware queries."""

import ctypes
from ctypes import c_char, c_int, c_int32, c_uint32, c_void_p

from .cfutils import (
    CF,
    CFAllocatorRef,
    CFDictionaryRef,
    CFMutableDictionaryRef,
    cfdata_get_bytes,
    cfdict_get_val,
    cfrelease,
    from_cfstr,
    kCFAllocatorDefault,
)

# ── Load IOKit framework ─────────────────────────────────────────────────────

_iokit_path = "/System/Library/Frameworks/IOKit.framework/IOKit"
IOKit = ctypes.cdll.LoadLibrary(_iokit_path)

# ── IOService bindings ────────────────────────────────────────────────────────

IOKit.IOServiceMatching.argtypes = [ctypes.c_char_p]
IOKit.IOServiceMatching.restype = CFMutableDictionaryRef

IOKit.IOServiceGetMatchingServices.argtypes = [
    c_uint32,
    CFDictionaryRef,
    ctypes.POINTER(c_uint32),
]
IOKit.IOServiceGetMatchingServices.restype = c_int32

IOKit.IOIteratorNext.argtypes = [c_uint32]
IOKit.IOIteratorNext.restype = c_uint32

IOKit.IORegistryEntryGetName.argtypes = [c_uint32, ctypes.c_char_p]
IOKit.IORegistryEntryGetName.restype = c_int32

IOKit.IORegistryEntryCreateCFProperties.argtypes = [
    c_uint32,
    ctypes.POINTER(CFMutableDictionaryRef),
    CFAllocatorRef,
    c_uint32,
]
IOKit.IORegistryEntryCreateCFProperties.restype = c_int32

IOKit.IOObjectRelease.argtypes = [c_uint32]
IOKit.IOObjectRelease.restype = c_uint32

# SMC bindings
IOKit.IOServiceOpen.argtypes = [c_uint32, c_uint32, c_uint32, ctypes.POINTER(c_uint32)]
IOKit.IOServiceOpen.restype = c_int32

IOKit.IOServiceClose.argtypes = [c_uint32]
IOKit.IOServiceClose.restype = c_int32

IOKit.IOConnectCallStructMethod.argtypes = [
    c_uint32,  # connection
    c_uint32,  # selector
    c_void_p,  # input struct
    ctypes.c_size_t,  # input size
    c_void_p,  # output struct
    ctypes.POINTER(ctypes.c_size_t),  # output size
]
IOKit.IOConnectCallStructMethod.restype = c_int32

# mach_task_self
_libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")
_libc.mach_task_self.argtypes = []
_libc.mach_task_self.restype = c_uint32


def mach_task_self() -> int:
    return _libc.mach_task_self()


# ── IOServiceIterator ─────────────────────────────────────────────────────────


class IOServiceIterator:
    """Iterator over IOService entries matching a given service name."""

    def __init__(self, service_name: str):
        self._existing = c_uint32(0)
        matching = IOKit.IOServiceMatching(service_name.encode("utf-8"))
        ret = IOKit.IOServiceGetMatchingServices(
            0, matching, ctypes.byref(self._existing)
        )
        if ret != 0:
            raise RuntimeError(f"IOServiceGetMatchingServices failed for {service_name}: {ret}")

    def __iter__(self):
        return self

    def __next__(self) -> tuple[int, str]:
        entry = IOKit.IOIteratorNext(self._existing)
        if entry == 0:
            raise StopIteration
        name_buf = ctypes.create_string_buffer(128)
        ret = IOKit.IORegistryEntryGetName(entry, name_buf)
        if ret != 0:
            IOKit.IOObjectRelease(entry)
            raise StopIteration
        name = name_buf.value.decode("utf-8")
        return (entry, name)

    def __del__(self):
        if self._existing.value:
            IOKit.IOObjectRelease(self._existing)


def get_entry_properties(entry: int) -> CFDictionaryRef:
    """Get all properties of an IORegistry entry as a CFDictionary."""
    props = CFMutableDictionaryRef()
    ret = IOKit.IORegistryEntryCreateCFProperties(
        entry, ctypes.byref(props), kCFAllocatorDefault, 0
    )
    if ret != 0:
        raise RuntimeError(f"IORegistryEntryCreateCFProperties failed: {ret}")
    return props


# ── GPU frequency table ───────────────────────────────────────────────────────


def _parse_dvfs_pairs(data: bytes) -> tuple[list[int], list[int]]:
    """Parse DVFS (Dynamic Voltage Frequency Scaling) pairs from raw bytes.

    Data is pairs of (freq, voltage) as 4-byte little-endian uint32 each.
    Returns (voltages, frequencies).
    """
    import struct

    count = len(data) // 8
    freqs = []
    volts = []
    for i in range(count):
        offset = i * 8
        freq = struct.unpack_from("<I", data, offset)[0]
        volt = struct.unpack_from("<I", data, offset + 4)[0]
        freqs.append(freq)
        volts.append(volt)
    return volts, freqs


def get_gpu_freq_table() -> list[int]:
    """Read GPU frequency table from IORegistry (AppleARMIODevice).

    Matches mactop's loadGpuFrequencies strategy:
    1. Search both 'pmgr' and 'clpc' devices
    2. Try 'voltage-states9-sram' or 'voltage-states9' first
    3. Fall back to any 'voltage-states*' key with valid GPU-range freqs

    Returns list of non-zero frequencies in MHz.
    """
    import struct

    try:
        for entry, name in IOServiceIterator("AppleARMIODevice"):
            if name not in ("pmgr", "clpc"):
                IOKit.IOObjectRelease(entry)
                continue

            props = get_entry_properties(entry)

            # Strategy 1: Try preferred keys directly
            best_raw = None
            for key_name in ("voltage-states9-sram", "voltage-states9"):
                data_ref = cfdict_get_val(props, key_name)
                if data_ref:
                    best_raw = cfdata_get_bytes(data_ref)
                    break

            # Strategy 2: Fall back to any voltage-states* with valid freqs
            if best_raw is None:
                count = CF.CFDictionaryGetCount(props)
                if count > 0:
                    keys_arr = (c_void_p * count)()
                    vals_arr = (c_void_p * count)()
                    CF.CFDictionaryGetKeysAndValues(props, keys_arr, vals_arr)

                    best_max_freq = 0xFFFFFFFF
                    for i in range(count):
                        key_str = from_cfstr(keys_arr[i])
                        if not key_str.startswith("voltage-states"):
                            continue
                        raw = cfdata_get_bytes(vals_arr[i])
                        n_entries = len(raw) // 8
                        current_max = 0
                        valid_count = 0
                        for j in range(n_entries):
                            freq = struct.unpack_from("<I", raw, j * 8)[0]
                            if freq > 100_000_000:  # > 100 MHz in Hz
                                valid_count += 1
                                current_max = max(current_max, freq)
                        if valid_count > 0 and current_max < best_max_freq:
                            best_max_freq = current_max
                            best_raw = raw

            if best_raw is not None:
                _, freqs = _parse_dvfs_pairs(best_raw)
                freq_mhz = [f // 1_000_000 for f in freqs if f // 1_000_000 > 0]
                cfrelease(props)
                IOKit.IOObjectRelease(entry)
                return freq_mhz

            cfrelease(props)
            IOKit.IOObjectRelease(entry)
    except RuntimeError:
        pass
    return []
