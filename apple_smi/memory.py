"""Unified memory and swap usage via libc syscalls."""

import ctypes
import ctypes.util
from ctypes import c_int, c_uint32, c_uint64, c_ulong
from dataclasses import dataclass

_libc = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")

# ── sysctl for total memory ──────────────────────────────────────────────────

_libc.sysctl.argtypes = [
    ctypes.POINTER(c_int),  # name
    c_uint32,  # namelen
    ctypes.c_void_p,  # oldp
    ctypes.POINTER(ctypes.c_size_t),  # oldlenp
    ctypes.c_void_p,  # newp
    ctypes.c_size_t,  # newlen
]
_libc.sysctl.restype = c_int

# sysconf for page size
_libc.sysconf.argtypes = [c_int]
_libc.sysconf.restype = ctypes.c_long

# host_statistics64
_libc.host_statistics64.argtypes = [
    c_uint32,  # host_priv
    c_int,  # flavor
    ctypes.c_void_p,  # host_info_out
    ctypes.POINTER(c_uint32),  # host_info_outCnt
]
_libc.host_statistics64.restype = c_int

_libc.mach_host_self.argtypes = []
_libc.mach_host_self.restype = c_uint32

# Constants
CTL_HW = 6
HW_MEMSIZE = 24
CTL_VM = 2
VM_SWAPUSAGE = 5
HOST_VM_INFO64 = 4
HOST_VM_INFO64_COUNT = 38  # sizeof(vm_statistics64_data_t) / sizeof(integer_t)
_SC_PAGESIZE = 29


@dataclass
class MemoryInfo:
    """System memory usage information."""

    ram_total: int = 0  # bytes
    ram_used: int = 0  # bytes
    swap_total: int = 0  # bytes
    swap_used: int = 0  # bytes


# ── vm_statistics64 structure ─────────────────────────────────────────────────
# Must match the macOS kernel structure layout


class _VMStatistics64(ctypes.Structure):
    _fields_ = [
        ("free_count", c_uint32),
        ("active_count", c_uint32),
        ("inactive_count", c_uint32),
        ("wire_count", c_uint32),
        ("zero_fill_count", c_uint64),
        ("reactivations", c_uint64),
        ("pageins", c_uint64),
        ("pageouts", c_uint64),
        ("faults", c_uint64),
        ("cow_faults", c_uint64),
        ("lookups", c_uint64),
        ("hits", c_uint64),
        ("purges", c_uint64),
        ("purgeable_count", c_uint32),
        ("speculative_count", c_uint32),
        ("decompressions", c_uint64),
        ("compressions", c_uint64),
        ("swapins", c_uint64),
        ("swapouts", c_uint64),
        ("compressor_page_count", c_uint32),
        ("throttled_count", c_uint32),
        ("external_page_count", c_uint32),
        ("internal_page_count", c_uint32),
        ("total_uncompressed_pages_in_compressor", c_uint64),
    ]


# ── xsw_usage structure ──────────────────────────────────────────────────────


class _XSwUsage(ctypes.Structure):
    _fields_ = [
        ("xsu_total", c_uint64),
        ("xsu_avail", c_uint64),
        ("xsu_used", c_uint64),
        ("xsu_pagesize", c_uint32),
        ("xsu_encrypted", ctypes.c_bool),
    ]


def get_memory_info() -> MemoryInfo:
    """Get current memory and swap usage."""
    info = MemoryInfo()

    # ── Total RAM ─────────────────────────────────────────────────────────
    name = (c_int * 2)(CTL_HW, HW_MEMSIZE)
    total = c_uint64(0)
    size = ctypes.c_size_t(ctypes.sizeof(c_uint64))
    ret = _libc.sysctl(name, 2, ctypes.byref(total), ctypes.byref(size), None, 0)
    if ret == 0:
        info.ram_total = total.value

    # ── RAM usage via host_statistics64 ───────────────────────────────────
    count = c_uint32(HOST_VM_INFO64_COUNT)
    stats = _VMStatistics64()
    ret = _libc.host_statistics64(
        _libc.mach_host_self(),
        HOST_VM_INFO64,
        ctypes.byref(stats),
        ctypes.byref(count),
    )
    if ret == 0:
        page_size = _libc.sysconf(_SC_PAGESIZE)
        used_pages = (
            stats.active_count
            + stats.inactive_count
            + stats.wire_count
            + stats.speculative_count
            + stats.compressor_page_count
            - stats.purgeable_count
            - stats.external_page_count
        )
        info.ram_used = used_pages * page_size

    # ── Swap usage ────────────────────────────────────────────────────────
    name = (c_int * 2)(CTL_VM, VM_SWAPUSAGE)
    xsw = _XSwUsage()
    size = ctypes.c_size_t(ctypes.sizeof(_XSwUsage))
    ret = _libc.sysctl(name, 2, ctypes.byref(xsw), ctypes.byref(size), None, 0)
    if ret == 0:
        info.swap_total = xsw.xsu_total
        info.swap_used = xsw.xsu_used

    return info
