"""Core Foundation helpers via ctypes for macOS framework interop."""

import ctypes
import ctypes.util
from ctypes import (
    POINTER,
    c_bool,
    c_char_p,
    c_int,
    c_int32,
    c_int64,
    c_long,
    c_uint32,
    c_void_p,
)

# ── Load Core Foundation ──────────────────────────────────────────────────────

_cf_path = "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
CF = ctypes.cdll.LoadLibrary(_cf_path)

# Type aliases
CFAllocatorRef = c_void_p
CFTypeRef = c_void_p
CFStringRef = c_void_p
CFNumberRef = c_void_p
CFDictionaryRef = c_void_p
CFMutableDictionaryRef = c_void_p
CFArrayRef = c_void_p
CFDataRef = c_void_p
CFIndex = c_long

# Constants
kCFAllocatorDefault = None  # NULL
kCFAllocatorNull = c_void_p.in_dll(CF, "kCFAllocatorNull")
kCFStringEncodingUTF8 = 0x08000100
kCFNumberSInt32Type = 3
kCFBooleanTrue = c_void_p.in_dll(CF, "kCFBooleanTrue")

# Callback structs (opaque, pass as pointers)
kCFTypeDictionaryKeyCallBacks = c_void_p.in_dll(CF, "kCFTypeDictionaryKeyCallBacks")
kCFTypeDictionaryValueCallBacks = c_void_p.in_dll(
    CF, "kCFTypeDictionaryValueCallBacks"
)

# ── CFRelease ─────────────────────────────────────────────────────────────────

CF.CFRelease.argtypes = [CFTypeRef]
CF.CFRelease.restype = None


def cfrelease(ref: c_void_p) -> None:
    """Release a Core Foundation object."""
    if ref:
        CF.CFRelease(ref)


# ── CFString ──────────────────────────────────────────────────────────────────

CF.CFStringCreateWithBytes.argtypes = [
    CFAllocatorRef,
    c_char_p,
    CFIndex,
    c_uint32,
    c_bool,
]
CF.CFStringCreateWithBytes.restype = CFStringRef

CF.CFStringGetCString.argtypes = [CFStringRef, c_char_p, CFIndex, c_uint32]
CF.CFStringGetCString.restype = c_bool

CF.CFStringGetLength.argtypes = [CFStringRef]
CF.CFStringGetLength.restype = CFIndex


def cfstr(s: str) -> CFStringRef:
    """Create a CFString from a Python string. Caller must CFRelease."""
    encoded = s.encode("utf-8")
    return CF.CFStringCreateWithBytes(
        kCFAllocatorDefault,
        encoded,
        len(encoded),
        kCFStringEncodingUTF8,
        False,
    )


def from_cfstr(ref: CFStringRef) -> str:
    """Convert a CFString to a Python string. Does NOT release the CFString."""
    if not ref:
        return ""
    buf = ctypes.create_string_buffer(1024)
    if CF.CFStringGetCString(ref, buf, 1024, kCFStringEncodingUTF8):
        return buf.value.decode("utf-8")
    return ""


# ── CFNumber ──────────────────────────────────────────────────────────────────

CF.CFNumberCreate.argtypes = [CFAllocatorRef, CFIndex, c_void_p]
CF.CFNumberCreate.restype = CFNumberRef


def cfnum(val: int) -> CFNumberRef:
    """Create a CFNumber (SInt32) from a Python int. Caller must CFRelease."""
    v = c_int32(val)
    return CF.CFNumberCreate(kCFAllocatorDefault, kCFNumberSInt32Type, ctypes.byref(v))


# ── CFDictionary ──────────────────────────────────────────────────────────────

CF.CFDictionaryCreate.argtypes = [
    CFAllocatorRef,
    POINTER(c_void_p),
    POINTER(c_void_p),
    CFIndex,
    c_void_p,  # key callbacks
    c_void_p,  # value callbacks
]
CF.CFDictionaryCreate.restype = CFDictionaryRef

CF.CFDictionaryGetCount.argtypes = [CFDictionaryRef]
CF.CFDictionaryGetCount.restype = CFIndex

CF.CFDictionaryGetValue.argtypes = [CFDictionaryRef, c_void_p]
CF.CFDictionaryGetValue.restype = c_void_p

CF.CFDictionaryCreateMutableCopy.argtypes = [
    CFAllocatorRef,
    CFIndex,
    CFDictionaryRef,
]
CF.CFDictionaryCreateMutableCopy.restype = CFMutableDictionaryRef

CF.CFDictionaryGetKeysAndValues.argtypes = [
    CFDictionaryRef,
    POINTER(c_void_p),
    POINTER(c_void_p),
]
CF.CFDictionaryGetKeysAndValues.restype = None


def cfdict_get_val(d: CFDictionaryRef, key: str) -> c_void_p | None:
    """Get a value from a CFDictionary by string key. Returns None if not found."""
    k = cfstr(key)
    val = CF.CFDictionaryGetValue(d, k)
    cfrelease(k)
    return val if val else None


# ── CFArray ───────────────────────────────────────────────────────────────────

CF.CFArrayGetCount.argtypes = [CFArrayRef]
CF.CFArrayGetCount.restype = CFIndex

CF.CFArrayGetValueAtIndex.argtypes = [CFArrayRef, CFIndex]
CF.CFArrayGetValueAtIndex.restype = c_void_p

# ── CFData ────────────────────────────────────────────────────────────────────

CF.CFDataGetLength.argtypes = [CFDataRef]
CF.CFDataGetLength.restype = CFIndex

CF.CFDataGetBytes.argtypes = [CFDataRef, c_int64, c_int64, c_void_p]
CF.CFDataGetBytes.restype = None


def cfdata_get_bytes(data_ref: CFDataRef) -> bytes:
    """Read all bytes from a CFData object."""
    length = CF.CFDataGetLength(data_ref)
    buf = ctypes.create_string_buffer(length)
    # CFRange is {location, length} passed as two args on ARM64
    CF.CFDataGetBytes(data_ref, 0, length, buf)
    return buf.raw
