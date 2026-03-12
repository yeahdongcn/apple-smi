"""IOReport private framework bindings for GPU/CPU metrics sampling."""

import ctypes
import time
from ctypes import c_int, c_int32, c_int64, c_uint64, c_void_p
from dataclasses import dataclass, field

from .cfutils import (
    CF,
    CFDictionaryRef,
    CFMutableDictionaryRef,
    CFStringRef,
    CFTypeRef,
    cfdict_get_val,
    cfrelease,
    cfstr,
    from_cfstr,
    kCFAllocatorDefault,
)

# ── Load IOReport library ─────────────────────────────────────────────────────

_ioreport_path = "/usr/lib/libIOReport.dylib"
IOR = ctypes.cdll.LoadLibrary(_ioreport_path)

# IOReport function signatures
IOR.IOReportCopyAllChannels.argtypes = [c_uint64, c_uint64]
IOR.IOReportCopyAllChannels.restype = CFDictionaryRef

IOR.IOReportCopyChannelsInGroup.argtypes = [
    CFStringRef,
    CFStringRef,
    c_uint64,
    c_uint64,
    c_uint64,
]
IOR.IOReportCopyChannelsInGroup.restype = CFDictionaryRef

IOR.IOReportMergeChannels.argtypes = [CFDictionaryRef, CFDictionaryRef, CFTypeRef]
IOR.IOReportMergeChannels.restype = None

IOR.IOReportCreateSubscription.argtypes = [
    c_void_p,  # NULL
    CFMutableDictionaryRef,
    ctypes.POINTER(CFMutableDictionaryRef),
    c_uint64,
    CFTypeRef,
]
IOR.IOReportCreateSubscription.restype = c_void_p  # IOReportSubscriptionRef

IOR.IOReportCreateSamples.argtypes = [
    c_void_p,  # subscription
    CFMutableDictionaryRef,
    CFTypeRef,
]
IOR.IOReportCreateSamples.restype = CFDictionaryRef

IOR.IOReportCreateSamplesDelta.argtypes = [
    CFDictionaryRef,
    CFDictionaryRef,
    CFTypeRef,
]
IOR.IOReportCreateSamplesDelta.restype = CFDictionaryRef

IOR.IOReportChannelGetGroup.argtypes = [CFDictionaryRef]
IOR.IOReportChannelGetGroup.restype = CFStringRef

IOR.IOReportChannelGetSubGroup.argtypes = [CFDictionaryRef]
IOR.IOReportChannelGetSubGroup.restype = CFStringRef

IOR.IOReportChannelGetChannelName.argtypes = [CFDictionaryRef]
IOR.IOReportChannelGetChannelName.restype = CFStringRef

IOR.IOReportSimpleGetIntegerValue.argtypes = [CFDictionaryRef, c_int32]
IOR.IOReportSimpleGetIntegerValue.restype = c_int64

IOR.IOReportChannelGetUnitLabel.argtypes = [CFDictionaryRef]
IOR.IOReportChannelGetUnitLabel.restype = CFStringRef

IOR.IOReportStateGetCount.argtypes = [CFDictionaryRef]
IOR.IOReportStateGetCount.restype = c_int32

IOR.IOReportStateGetNameForIndex.argtypes = [CFDictionaryRef, c_int32]
IOR.IOReportStateGetNameForIndex.restype = CFStringRef

IOR.IOReportStateGetResidency.argtypes = [CFDictionaryRef, c_int32]
IOR.IOReportStateGetResidency.restype = c_int64


# ── Helper functions ──────────────────────────────────────────────────────────


def _get_channel_group(item: CFDictionaryRef) -> str:
    ref = IOR.IOReportChannelGetGroup(item)
    return from_cfstr(ref) if ref else ""


def _get_channel_subgroup(item: CFDictionaryRef) -> str:
    ref = IOR.IOReportChannelGetSubGroup(item)
    return from_cfstr(ref) if ref else ""


def _get_channel_name(item: CFDictionaryRef) -> str:
    ref = IOR.IOReportChannelGetChannelName(item)
    return from_cfstr(ref) if ref else ""


def _get_channel_unit(item: CFDictionaryRef) -> str:
    ref = IOR.IOReportChannelGetUnitLabel(item)
    return from_cfstr(ref).strip() if ref else ""


def _get_residencies(item: CFDictionaryRef) -> list[tuple[str, int]]:
    """Get state residency data from an IOReport channel item."""
    count = IOR.IOReportStateGetCount(item)
    result = []
    for i in range(count):
        name_ref = IOR.IOReportStateGetNameForIndex(item, i)
        name = from_cfstr(name_ref) if name_ref else ""
        val = IOR.IOReportStateGetResidency(item, i)
        result.append((name, val))
    return result


def _get_simple_value(item: CFDictionaryRef) -> int:
    """Get simple integer value from an IOReport channel item."""
    return IOR.IOReportSimpleGetIntegerValue(item, 0)


# ── IOReport channel item ────────────────────────────────────────────────────


@dataclass
class IOReportChannelItem:
    """A single channel item from an IOReport sample.

    All data is pre-extracted during iteration so no raw CF refs are held.
    """

    group: str
    subgroup: str
    channel: str
    unit: str
    simple_value: int = 0  # pre-extracted integer value
    residencies: list[tuple[str, int]] = field(
        default_factory=list
    )  # pre-extracted state residencies


def compute_watts(simple_value: int, unit: str, duration_ms: int) -> float:
    """Convert IOReport energy value to Watts given the unit and sample duration.

    Matches mactop's energyToWatts: defaults to µJ if unit is unknown/empty.
    """
    if simple_value < 0:
        return 0.0  # Invalid / not applicable
    val_per_sec = simple_value / (duration_ms / 1000.0)
    match unit:
        case "mJ":
            return val_per_sec / 1e3
        case "uJ":
            return val_per_sec / 1e6
        case "nJ":
            return val_per_sec / 1e9
        case _:
            # Default to µJ like mactop does for unknown/empty units
            return val_per_sec / 1e6


# ── IOReportSampler ───────────────────────────────────────────────────────────


class IOReportSampler:
    """Manages IOReport subscriptions and sampling for GPU/CPU metrics."""

    def __init__(self, channels: list[tuple[str, str | None]]):
        """Initialize with a list of (group, subgroup_or_None) channel specs."""
        self._chan = self._build_channels(channels)
        self._subs = self._create_subscription(self._chan)
        self._prev_sample: CFDictionaryRef | None = None

    @staticmethod
    def _build_channels(
        items: list[tuple[str, str | None]],
    ) -> CFMutableDictionaryRef:
        """Build merged IOReport channel dictionary."""
        channel_dicts = []
        for group, subgroup in items:
            g = cfstr(group)
            s = cfstr(subgroup) if subgroup else None
            chan = IOR.IOReportCopyChannelsInGroup(g, s, 0, 0, 0)
            channel_dicts.append(chan)
            cfrelease(g)
            if s:
                cfrelease(s)

        if not channel_dicts:
            raise RuntimeError("No IOReport channels found")

        # Merge all channel dicts into the first one
        base = channel_dicts[0]
        for i in range(1, len(channel_dicts)):
            IOR.IOReportMergeChannels(base, channel_dicts[i], None)

        # Create a mutable copy
        size = CF.CFDictionaryGetCount(base)
        merged = CF.CFDictionaryCreateMutableCopy(kCFAllocatorDefault, size, base)

        for d in channel_dicts:
            cfrelease(d)

        if not cfdict_get_val(merged, "IOReportChannels"):
            cfrelease(merged)
            raise RuntimeError("Failed to get IOReport channels")

        return merged

    @staticmethod
    def _create_subscription(chan: CFMutableDictionaryRef) -> c_void_p:
        """Create an IOReport subscription."""
        sub_dict = CFMutableDictionaryRef()
        subs = IOR.IOReportCreateSubscription(
            None, chan, ctypes.byref(sub_dict), 0, None
        )
        if not subs:
            raise RuntimeError("Failed to create IOReport subscription")
        return subs

    def _take_sample(self) -> CFDictionaryRef:
        """Take a single IOReport sample."""
        return IOR.IOReportCreateSamples(self._subs, self._chan, None)

    def get_sample(self, duration_ms: int) -> list[IOReportChannelItem]:
        """Take two samples separated by duration_ms and return the delta.

        All data is extracted from the delta before releasing it, so the
        returned items contain only Python objects (no dangling CF refs).
        """
        sample1 = self._take_sample()
        time.sleep(duration_ms / 1000.0)
        sample2 = self._take_sample()

        delta = IOR.IOReportCreateSamplesDelta(sample1, sample2, None)
        cfrelease(sample1)
        cfrelease(sample2)

        # Extract all data BEFORE releasing delta
        items = self._extract_items(delta)
        cfrelease(delta)
        return items

    @staticmethod
    def _extract_items(sample: CFDictionaryRef) -> list[IOReportChannelItem]:
        """Extract all channel data from a sample, returning pure Python objects.

        This must be called while the sample CF object is still alive.
        """
        channels_ref = cfdict_get_val(sample, "IOReportChannels")
        if not channels_ref:
            return []

        count = CF.CFArrayGetCount(channels_ref)
        items = []
        for i in range(count):
            item_ref = CF.CFArrayGetValueAtIndex(channels_ref, i)

            # Pre-extract ALL data while the CF ref is valid
            group = _get_channel_group(item_ref)
            subgroup = _get_channel_subgroup(item_ref)
            channel = _get_channel_name(item_ref)
            unit = _get_channel_unit(item_ref)
            simple_value = _get_simple_value(item_ref)
            residencies = _get_residencies(item_ref)

            items.append(
                IOReportChannelItem(
                    group=group,
                    subgroup=subgroup,
                    channel=channel,
                    unit=unit,
                    simple_value=simple_value,
                    residencies=residencies,
                )
            )
        return items

    def __del__(self):
        if hasattr(self, "_chan") and self._chan:
            cfrelease(self._chan)
        if hasattr(self, "_prev_sample") and self._prev_sample:
            cfrelease(self._prev_sample)
