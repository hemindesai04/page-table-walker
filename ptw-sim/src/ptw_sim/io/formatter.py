"""
Output formatter for walk results — produces the serialized trace format.

This module formats WalkResult objects into the standardized trace JSON
format that can be consumed by the visualizer (or any other tool).

TRACE FORMAT (v1.0):
====================
{
    "format_version": "1.0",
    "generator": "ptw-sim",
    "scenario_name": "string",
    "description": "string",
    "timestamp": "ISO 8601",
    "input": {
        "virtual_address": "0x...",
        "access_type": "READ/WRITE/EXECUTE",
        "privilege_level": "EL0/EL1",
        "va_bits": 48,
        "pa_bits": 56
    },
    "configuration": {
        "architecture": { "granule_size_kb": 4, ... },
        "registers": { "TTBR0_EL1": "0x...", ... }
    },
    "result": {
        "status": "SUCCESS/S1_FAULT/S2_FAULT/S2_FINAL_FAULT",
        "final_pa": "0x...",
        "ipa": "0x...",
        "total_memory_accesses": 20
    },
    "walk_trace": {
        "events": [ ... ],
        "register_snapshots": [ ... ]
    },
    "fault": { ... },
    "final_permissions": { ... },
    "final_attributes": { ... }
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ptw_sim.core.walker import WalkResult, WalkStatus
from ptw_sim.io.parser import ScenarioConfig

# Current trace format version
TRACE_FORMAT_VERSION = "1.0"


@dataclass
class WalkOutput:
    """
    Formatted output for a page table walk.

    This wraps the WalkResult with scenario metadata for output.
    """

    scenario_name: str
    description: str
    timestamp: str
    input_config: Dict[str, Any]
    result: WalkResult
    config: Optional[ScenarioConfig] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (trace format v1.0)."""
        result_dict = self.result.to_dict()

        trace = {
            "format_version": TRACE_FORMAT_VERSION,
            "generator": "ptw-sim",
            "scenario_name": self.scenario_name,
            "description": self.description,
            "timestamp": self.timestamp,
            "input": self.input_config,
            "result": {
                "status": result_dict["status"],
                "final_pa": result_dict["output_pa"],
                "ipa": result_dict["ipa"],
                "total_memory_accesses": result_dict["total_memory_accesses"],
            },
            "walk_trace": {
                "events": result_dict["events"],
                "register_snapshots": result_dict["register_snapshots"],
            },
            "fault": result_dict["fault"],
            "final_permissions": result_dict["final_permissions"],
            "final_attributes": result_dict["final_attributes"],
        }

        # Include the full configuration so the visualizer has all context
        if self.config:
            trace["configuration"] = {
                "architecture": {
                    "granule_size_kb": self.config.architecture.granule_size_kb,
                    "va_bits": self.config.architecture.va_bits,
                    "pa_bits": self.config.architecture.pa_bits,
                    "ipa_bits": self.config.architecture.ipa_bits,
                    "feat_d128_enabled": self.config.architecture.feat_d128_enabled,
                },
                "registers": {
                    "TTBR0_EL1": self.config.registers.TTBR0_EL1,
                    "TTBR1_EL1": self.config.registers.TTBR1_EL1,
                    "VTTBR_EL2": self.config.registers.VTTBR_EL2,
                    "TCR_EL1": {
                        "T0SZ": self.config.registers.TCR_EL1.T0SZ,
                        "T1SZ": self.config.registers.TCR_EL1.T1SZ,
                    },
                    "VTCR_EL2": {
                        "T0SZ": self.config.registers.VTCR_EL2.T0SZ,
                        "SL0": self.config.registers.VTCR_EL2.SL0,
                    },
                },
            }

        return trace

    def to_json(self, indent: int = 2) -> str:
        """Convert to formatted JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def format_output(
    result: WalkResult,
    config: ScenarioConfig
) -> WalkOutput:
    """
    Format a WalkResult with scenario metadata.

    Args:
        result: The walk result to format.
        config: The scenario configuration.

    Returns:
        Formatted WalkOutput.
    """
    input_config = {
        "virtual_address": result.input_va.to_hex(),
        "access_type": config.memory_access.access_type,
        "privilege_level": config.memory_access.privilege_level,
        "va_bits": config.architecture.va_bits,
        "pa_bits": config.architecture.pa_bits,
    }

    return WalkOutput(
        scenario_name=config.scenario_name,
        description=config.description,
        timestamp=datetime.now().isoformat(),
        input_config=input_config,
        result=result,
        config=config,
    )


def save_output(
    output: WalkOutput,
    file_path: str | Path,
    pretty: bool = True
) -> None:
    """
    Save formatted output to a trace JSON file.

    Args:
        output: The formatted output.
        file_path: Destination file path.
        pretty: If True, format with indentation.
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    indent = 2 if pretty else None
    with open(path, "w") as f:
        json.dump(output.to_dict(), f, indent=indent)


def generate_summary(result: WalkResult) -> str:
    """
    Generate a human-readable summary of the walk result.

    Args:
        result: The walk result.

    Returns:
        Multi-line summary string.
    """
    lines = []

    lines.append("=" * 60)
    lines.append("PAGE TABLE WALK SUMMARY")
    lines.append("=" * 60)

    lines.append(f"Input VA: {result.input_va.to_hex()}")
    lines.append(f"  L0 Index: {result.input_va.l0_index:#05x}")
    lines.append(f"  L1 Index: {result.input_va.l1_index:#05x}")
    lines.append(f"  L2 Index: {result.input_va.l2_index:#05x}")
    lines.append(f"  L3 Index: {result.input_va.l3_index:#05x}")
    lines.append(f"  Page Offset: {result.input_va.page_offset:#05x}")

    lines.append("-" * 60)

    if result.status == WalkStatus.SUCCESS:
        lines.append(f"✓ Translation SUCCESSFUL")
        lines.append(f"  IPA: {result.ipa.to_hex() if result.ipa else 'N/A'}")
        lines.append(f"  PA:  {result.output_pa.to_hex() if result.output_pa else 'N/A'}")
    else:
        lines.append(f"✗ Translation FAILED: {result.status.name}")
        if result.fault:
            lines.append(f"  Fault: {result.fault.fault_type.name}")
            lines.append(f"  Stage: {result.fault.stage}, Level: {result.fault.level}")
            lines.append(f"  Message: {result.fault.message}")

    lines.append("-" * 60)
    lines.append(f"Total Memory Accesses: {result.total_memory_accesses}")

    if result.final_permissions:
        lines.append("Final Permissions:")
        p = result.final_permissions
        lines.append(f"  EL0: R={p.read_el0}, W={p.write_el0}, X={p.execute_el0}")
        lines.append(f"  EL1: R={p.read_el1}, W={p.write_el1}, X={p.execute_el1}")

    lines.append("=" * 60)

    return "\n".join(lines)
