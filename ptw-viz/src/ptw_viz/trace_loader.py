"""
Trace loader for the visualizer.

This module loads and validates serialized walk trace JSON files produced
by ptw-sim. It provides a clean, typed interface to the trace data
without any dependency on the simulator package.

The trace format is versioned — the loader validates the format_version
and provides helpful errors for incompatible files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


SUPPORTED_FORMAT_VERSIONS = {"1.0"}


@dataclass
class TraceEvent:
    """A single walk event from the trace."""

    event_id: int
    event_type: str
    stage: int
    level: int
    purpose: str
    address: str
    descriptor_value: str
    result: str
    output: str


@dataclass
class TraceData:
    """
    Parsed and validated walk trace data.

    This is the visualizer's view of a trace — all data needed to
    render the visualization without needing the simulator.
    """

    format_version: str
    generator: str
    scenario_name: str
    description: str
    timestamp: str

    # Input configuration
    virtual_address: str
    access_type: str
    privilege_level: str
    va_bits: int
    pa_bits: int

    # Result summary
    status: str
    final_pa: Optional[str]
    ipa: Optional[str]
    total_memory_accesses: int

    # Walk events
    events: List[TraceEvent]
    register_snapshots: List[Dict[str, Any]]

    # Fault (if any)
    fault: Optional[Dict[str, Any]]

    # Permissions and attributes
    final_permissions: Optional[Dict[str, Any]]
    final_attributes: Optional[Dict[str, Any]]

    # Full configuration (optional, for detailed display)
    configuration: Optional[Dict[str, Any]] = None

    # Computed properties for convenience
    @property
    def is_success(self) -> bool:
        return self.status == "SUCCESS"

    @property
    def s1_events(self) -> List[TraceEvent]:
        return [e for e in self.events if e.stage == 1]

    @property
    def s2_events(self) -> List[TraceEvent]:
        return [e for e in self.events if e.stage == 2]

    @property
    def va_l0_index(self) -> str:
        """Extract L0 index from VA — computed from the hex value."""
        va_int = int(self.virtual_address, 16)
        return f"0x{(va_int >> 39) & 0x1FF:03X}"

    @property
    def va_l1_index(self) -> str:
        va_int = int(self.virtual_address, 16)
        return f"0x{(va_int >> 30) & 0x1FF:03X}"

    @property
    def va_l2_index(self) -> str:
        va_int = int(self.virtual_address, 16)
        return f"0x{(va_int >> 21) & 0x1FF:03X}"

    @property
    def va_l3_index(self) -> str:
        va_int = int(self.virtual_address, 16)
        return f"0x{(va_int >> 12) & 0x1FF:03X}"

    @property
    def va_page_offset(self) -> str:
        va_int = int(self.virtual_address, 16)
        return f"0x{va_int & 0xFFF:03X}"


def load_trace(file_path: str | Path) -> TraceData:
    """
    Load a walk trace from a JSON file.

    Args:
        file_path: Path to trace JSON file (produced by ptw-sim).

    Returns:
        Parsed TraceData.

    Raises:
        FileNotFoundError: If trace file doesn't exist.
        ValueError: If trace format is invalid or unsupported.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    with open(path, "r") as f:
        raw = json.load(f)

    return parse_trace_dict(raw)


def parse_trace_dict(raw: Dict[str, Any]) -> TraceData:
    """
    Parse a trace dictionary into a TraceData object.

    Args:
        raw: Raw dictionary from JSON.

    Returns:
        Parsed TraceData.

    Raises:
        ValueError: If format is invalid.
    """
    # Validate format version
    version = raw.get("format_version")
    if version is None:
        raise ValueError(
            "Missing 'format_version' in trace file. "
            "This file may not have been produced by ptw-sim. "
            "Expected format_version: 1.0"
        )
    if version not in SUPPORTED_FORMAT_VERSIONS:
        raise ValueError(
            f"Unsupported trace format version: {version}. "
            f"Supported versions: {SUPPORTED_FORMAT_VERSIONS}"
        )

    # Parse input section
    inp = raw.get("input", {})

    # Parse result section
    result = raw.get("result", {})

    # Parse walk trace
    trace = raw.get("walk_trace", {})
    events = []
    for e in trace.get("events", []):
        events.append(TraceEvent(
            event_id=e.get("event_id", 0),
            event_type=e.get("event_type", "T"),
            stage=e.get("stage", 0),
            level=e.get("level", 0),
            purpose=e.get("purpose", ""),
            address=e.get("address", "0x0"),
            descriptor_value=e.get("descriptor_value", "0x0"),
            result=e.get("result", ""),
            output=e.get("output", "0x0"),
        ))

    return TraceData(
        format_version=version,
        generator=raw.get("generator", "unknown"),
        scenario_name=raw.get("scenario_name", "unnamed"),
        description=raw.get("description", ""),
        timestamp=raw.get("timestamp", ""),
        virtual_address=inp.get("virtual_address", "0x0"),
        access_type=inp.get("access_type", "READ"),
        privilege_level=inp.get("privilege_level", "EL0"),
        va_bits=inp.get("va_bits", 48),
        pa_bits=inp.get("pa_bits", 56),
        status=result.get("status", "UNKNOWN"),
        final_pa=result.get("final_pa"),
        ipa=result.get("ipa"),
        total_memory_accesses=result.get("total_memory_accesses", 0),
        events=events,
        register_snapshots=trace.get("register_snapshots", []),
        fault=raw.get("fault"),
        final_permissions=raw.get("final_permissions"),
        final_attributes=raw.get("final_attributes"),
        configuration=raw.get("configuration"),
    )
